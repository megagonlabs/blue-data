"""
Redis-backed DataRegistry demo — Northwind database.

Backend stack:
  - Registry store : RedisJSONSource   (Redis Stack JSON.GET / JSON.SET)
  - Search index   : RedisVectorSource (Redis Stack FT.CREATE / FT.SEARCH)
  - Data source    : PostgresDBSource  (Northwind DB, falls back to SQLite)

Sections:
  1.  Connectivity check — Redis Stack + Postgres/SQLite
  2.  Setup — DataRegistry with Redis backends
  3.  Register source and sync schema
  3b. Full hierarchy walk — source → database → collection → entity → attribute
  4.  Set descriptions on key entities
  5.  collect_source_stats — entity + attribute level
  6.  enrich_source — semantic type inference
  7.  search_records — hybrid BM25 + vector
  8.  Keyword-only search via search_engine.keyword_search
  9.  Namespace isolation — two independent namespaces in one Redis
  10. dumps / loads — serialize registry to JSON and restore

Environment variables (all optional):
  REDIS_HOST  (default: localhost)
  REDIS_PORT  (default: 6379)
  PGHOST      (default: localhost)
  PGPORT      (default: 5432)
  PGUSER      (default: postgres)
  PGPASSWORD  (default: "")
  PGDATABASE  (default: northwind)

Run from lib/:
    PYTHONPATH=src/blue-data python3 ../examples/redis_demo.py
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile

DIVIDER = "-" * 60
DIM = 64


# ---------------------------------------------------------------------------
# Embedding (deterministic, no model needed)
# ---------------------------------------------------------------------------

def make_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------------------------------------------------------------------------
# 1. Connectivity checks
# ---------------------------------------------------------------------------

print(DIVIDER)
print("1. Connectivity checks")
print(DIVIDER)

# --- Redis ---
try:
    import redis as _redis_lib
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource
    _redis_imports_ok = True
except ImportError as e:
    print(f"  [SKIP] Redis imports unavailable: {e}")
    print("  Install: pip install redis")
    _redis_imports_ok = False

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.environ.get("REDIS_PORT", "6379"))

_redis_available = False
if _redis_imports_ok:
    try:
        _probe = _redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        _probe.ping()
        _redis_available = True
        print(f"  Redis Stack: OK  ({REDIS_HOST}:{REDIS_PORT})")
    except Exception as e:
        print(f"  [SKIP] Redis Stack not reachable: {e}")
        print("  Start with: redis-stack-server")

if not _redis_available:
    print()
    print("Redis Stack is required for this demo. Exiting.")
    sys.exit(0)

# --- Data source: try Postgres first, fall back to SQLite ---
PGHOST     = os.environ.get("PGHOST",     "localhost")
PGPORT     = int(os.environ.get("PGPORT", "5432"))
PGUSER     = os.environ.get("PGUSER",     "postgres")
PGPASSWORD = os.environ.get("PGPASSWORD", "")
PGDATABASE = os.environ.get("PGDATABASE", "northwind")

_use_postgres = False
try:
    from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource
    _pg_source = PostgresDBSource(
        name="northwind",
        properties={
            "connection": {
                "host":     PGHOST,
                "port":     PGPORT,
                "user":     PGUSER,
                "password": PGPASSWORD,
                "database": PGDATABASE,
            }
        },
    )
    dbs = _pg_source.fetch_databases()
    if PGDATABASE in dbs:
        _use_postgres = True
        print(f"  PostgreSQL: OK  ({PGHOST}:{PGPORT}/{PGDATABASE})")
    else:
        print(f"  [FALLBACK] Database '{PGDATABASE}' not found in Postgres "
              f"(found: {dbs}). Using SQLite.")
except Exception as e:
    print(f"  [FALLBACK] Postgres unavailable: {e}")
    print("  Load Northwind:  psql -U postgres -c \"CREATE DATABASE northwind;\"")
    print("                   psql -U postgres -d northwind -f data/northwind_postgres.sql")

if not _use_postgres:
    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

    _demo_dir = tempfile.mkdtemp(prefix="northwind-demo-")
    _db_path  = os.path.join(_demo_dir, "northwind.db")
    _sql_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "northwind_sqlite.sql",
    )
    if not os.path.exists(_sql_file):
        print(f"  [SKIP] northwind_sqlite.sql not found at {_sql_file}")
        sys.exit(1)

    result = subprocess.run(
        ["sqlite3", _db_path],
        stdin=open(_sql_file),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("  [SKIP] sqlite3 load failed:", result.stderr)
        sys.exit(1)

    print(f"  SQLite Northwind loaded: {_db_path}")
    SOURCE_NAME = "northwind_sqlite"
    SOURCE_DB   = "northwind"
else:
    SOURCE_NAME = "northwind"
    SOURCE_DB   = PGDATABASE


# ---------------------------------------------------------------------------
# Namespace constants — unique to this demo run so we don't collide
# ---------------------------------------------------------------------------

import uuid as _uuid
_run_id       = _uuid.uuid4().hex[:8]
NAMESPACE     = f"demo-{_run_id}"
NAMESPACE2    = f"demo2-{_run_id}"
SCAN_PREFIX   = f"{NAMESPACE}-vec"
SCAN_PREFIX2  = f"{NAMESPACE2}-vec"
INDEX_NAME    = f"{NAMESPACE}-idx"
INDEX_NAME2   = f"{NAMESPACE2}-idx"


def _cleanup_redis(namespace: str, scan_prefix: str, index_name: str):
    """Delete all keys belonging to this demo run."""
    client = _redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    # registry keys
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=f"{namespace}:*", count=500)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
    # vector keys
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=f"{scan_prefix}*", count=500)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
    # search index (ignore if missing)
    try:
        client.execute_command("FT.DROPINDEX", index_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 2. Setup — DataRegistry with Redis backends
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("2. Setup — DataRegistry with Redis backends")
print(DIVIDER)

from blue_data.registry.data_registry import DataRegistry

json_store = RedisJSONSource(
    properties={
        "namespace": NAMESPACE,
        "connection": {"host": REDIS_HOST, "port": REDIS_PORT},
    }
)

vector_store = RedisVectorSource(
    name="vector",
    properties={
        "connection": {
            "host":        REDIS_HOST,
            "port":        REDIS_PORT,
            "scan_prefix": SCAN_PREFIX,
        }
    },
)

registry = DataRegistry(
    store=json_store,
    vector_source=vector_store,
    embedding_fn=make_embedding,
    vector_dim=DIM,
    index_name=INDEX_NAME,
    rebuild=True,
    hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
)

# Create the vector search index in Redis
vector_store.execute_query({
    "op":         "VECTOR.CREATE_INDEX",
    "index":      INDEX_NAME,
    "collection": "records",
    "dim":        DIM,
})

print(f"  Registry namespace : {NAMESPACE}")
print(f"  Vector scan_prefix : {SCAN_PREFIX}")
print(f"  Vector index       : {INDEX_NAME}")
print(f"  Store type         : {type(json_store).__name__}")
print(f"  Vector store type  : {type(vector_store).__name__}")


# ---------------------------------------------------------------------------
# 3. Register source and sync schema
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3. Register source and sync schema")
print(DIVIDER)

if _use_postgres:
    data_source = _pg_source
else:
    data_source = SQLiteDBSource(
        name=SOURCE_NAME,
        properties={"connection": {"database_directory": _demo_dir}},
    )

registry.register_source(data_source)
print(f"  Registered source  : {SOURCE_NAME}")

registry.sync_source(SOURCE_NAME, recursive=True)

dbs = [r["name"] for r in registry.list_source_databases(SOURCE_NAME)]
print(f"  Databases          : {dbs}")

collection = "public"
entities = [r["name"] for r in registry.list_collection_entities(SOURCE_NAME, SOURCE_DB, collection)]
print(f"  Entities in public : {sorted(entities)}")

schema_json = registry.get_source_database_collection_property(
    SOURCE_NAME, SOURCE_DB, collection, "schema"
)
if schema_json:
    schema = json.loads(schema_json) if isinstance(schema_json, str) else schema_json
    print(f"  Schema entity count: {len(schema.get('entities', {}))}")


# ---------------------------------------------------------------------------
# 3b. Walk the full hierarchy: source → database → collection → entity → attribute
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3b. Full hierarchy walk")
print(DIVIDER)

print(f"  source: {SOURCE_NAME}")

for db_record in registry.list_source_databases(SOURCE_NAME):
    db_name = db_record["name"]
    print(f"    database: {db_name}")

    for coll_record in registry.list_database_collections(SOURCE_NAME, db_name):
        coll_name = coll_record["name"]
        print(f"      collection: {coll_name}")

        entity_records = registry.list_collection_entities(SOURCE_NAME, db_name, coll_name)
        for ent_record in sorted(entity_records, key=lambda r: r["name"]):
            ent_name = ent_record["name"]
            attr_records = registry.list_entity_attributes(SOURCE_NAME, db_name, coll_name, ent_name)
            attr_names = sorted(r["name"] for r in attr_records)
            print(f"        entity: {ent_name:22s}  attributes: {attr_names}")

        rel_records = registry.list_collection_relations(SOURCE_NAME, db_name, coll_name)
        for rel_record in sorted(rel_records, key=lambda r: r["name"]):
            rel_name = rel_record["name"]
            rel_attr_records = registry.get_source_database_collection_relation_attributes(
                SOURCE_NAME, db_name, coll_name, rel_name
            )
            rel_attr_names = [r["name"] for r in rel_attr_records]
            print(f"        relation: {rel_name:20s}  attributes: {rel_attr_names}")


# ---------------------------------------------------------------------------
# 4. Set descriptions on key entities
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("4. Set descriptions")
print(DIVIDER)

descriptions = {
    "categories":    "Product category taxonomy",
    "customers":     "Customer accounts and contact information",
    "employees":     "Sales staff and their reporting structure",
    "orders":        "Customer purchase orders with freight and ship details",
    "order_details": "Line items linking orders to products with pricing",
    "products":      "Product catalog with pricing, stock, and category",
    "suppliers":     "Product supplier companies and contacts",
}

for entity, desc in descriptions.items():
    if entity in entities:
        registry.set_source_database_collection_entity_description(
            SOURCE_NAME, SOURCE_DB, collection, entity, desc
        )

registry.set_source_database_description(SOURCE_NAME, SOURCE_DB, "Northwind demo sales database")
registry.set_source_database_collection_description(SOURCE_NAME, SOURCE_DB, collection, "Default public schema")

print(f"  Set descriptions on {len(descriptions)} entities + database + collection")

orders_desc = registry.get_source_database_collection_entity_description(
    SOURCE_NAME, SOURCE_DB, collection, "orders"
)
print(f"  orders.description : {orders_desc}")


# ---------------------------------------------------------------------------
# 5. collect_source_stats — entity + attribute level
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("5. collect_source_stats")
print(DIVIDER)

# Collect at entity level (row counts)
for entity in entities[:3]:
    try:
        registry.collect_source_database_collection_entity_stats(
            SOURCE_NAME, SOURCE_DB, collection, entity
        )
        stats = registry.get_source_database_collection_entity_property(
            SOURCE_NAME, SOURCE_DB, collection, entity, "stats"
        )
        print(f"  {entity:20s} stats: {stats}")
    except Exception as e:
        print(f"  {entity:20s} stats: [skipped] {e}")

# Collect attribute-level stats for a key column
_stat_entity = "products" if "products" in entities else (list(entities)[0] if entities else None)
_stat_attr   = "unit_price" if "products" in entities else None

if _stat_entity and _stat_attr:
    attrs = [r["name"] for r in registry.list_entity_attributes(SOURCE_NAME, SOURCE_DB, collection, _stat_entity)]
    if _stat_attr in attrs:
        try:
            registry.collect_source_database_collection_entity_attribute_stats(
                SOURCE_NAME, SOURCE_DB, collection, _stat_entity, _stat_attr
            )
            attr_stats = registry.get_source_database_collection_entity_attribute_property(
                SOURCE_NAME, SOURCE_DB, collection, _stat_entity, _stat_attr, "stats"
            )
            print(f"  {_stat_entity}.{_stat_attr} stats: {attr_stats}")
        except Exception as e:
            print(f"  {_stat_entity}.{_stat_attr} stats: [skipped] {e}")


# ---------------------------------------------------------------------------
# 6. enrich_source — semantic type inference
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("6. enrich_source — semantic type inference")
print(DIVIDER)

try:
    registry.enrich_source(SOURCE_NAME)

    for entity, attr in [("customers", "contact_name"), ("orders", "order_date")]:
        if entity in entities:
            e_attrs = [r["name"] for r in registry.list_entity_attributes(SOURCE_NAME, SOURCE_DB, collection, entity)]
            if attr in e_attrs:
                sem = registry.get_source_database_collection_entity_attribute_property(
                    SOURCE_NAME, SOURCE_DB, collection, entity, attr, "value_semantics"
                )
                print(f"  {entity}.{attr:15s} → {sem}")
except Exception as e:
    print(f"  [skipped] enrich_source error: {e}")


# ---------------------------------------------------------------------------
# 7. search_records — hybrid BM25 + vector
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("7. search_records — hybrid BM25 + vector")
print(DIVIDER)

queries = [
    "customer purchase orders",
    "product pricing inventory",
    "employee sales representative",
]

for q in queries:
    results = registry.search_records(q)
    top = results[:3]
    label = f"'{q}'"
    print(f"  search({label[:35]:<37}):")
    for r in top:
        score = r.get("_score", 0)
        print(f"    [{score:.3f}] {r['name']:22s} — {r.get('description', '')[:55]}")

# Type-filtered search
type_results = registry.search_records("orders", type="entity")
print(f"  search('orders', type='entity')     : {[r['name'] for r in type_results]}")

# Scope-filtered search
scope_results = registry.search_records("products", scope=f"/source/{SOURCE_NAME}")
print(f"  search('products', scope=source)    : {[r['name'] for r in scope_results[:4]]}")


# ---------------------------------------------------------------------------
# 8. Keyword-only search via search_engine.keyword_search
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("8. Keyword-only search (BM25 only)")
print(DIVIDER)

for kw in ["sales", "freight", "supplier"]:
    kw_results = registry.search_engine.keyword_search(kw)
    hits = [r["record"]["name"] for r in kw_results[:3]]
    print(f"  keyword_search({kw!r:15s}): {hits}")


# ---------------------------------------------------------------------------
# 9. Namespace isolation — two independent namespaces in one Redis instance
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("9. Namespace isolation")
print(DIVIDER)

json_store2 = RedisJSONSource(
    properties={
        "namespace": NAMESPACE2,
        "connection": {"host": REDIS_HOST, "port": REDIS_PORT},
    }
)
vector_store2 = RedisVectorSource(
    name="vector2",
    properties={
        "connection": {
            "host":        REDIS_HOST,
            "port":        REDIS_PORT,
            "scan_prefix": SCAN_PREFIX2,
        }
    },
)

registry2 = DataRegistry(
    store=json_store2,
    vector_source=vector_store2,
    embedding_fn=make_embedding,
    vector_dim=DIM,
    index_name=INDEX_NAME2,
    rebuild=False,
)

try:
    vector_store2.execute_query({
        "op":         "VECTOR.CREATE_INDEX",
        "index":      INDEX_NAME2,
        "collection": "records",
        "dim":        DIM,
    })
except Exception:
    pass  # index may already exist from a previous run

registry2.register_record("warehouses", "entity", "/source/logistics", description="Warehouse locations")
registry2.register_record("shipments",  "entity", "/source/logistics", description="Outbound shipments")

# Verify the two namespaces don't bleed into each other
ns1_keys = list(json_store.data.keys())
ns2_keys = list(json_store2.data.keys())

print(f"  Namespace 1 ({NAMESPACE[:16]}...) key count: {len(ns1_keys)}")
print(f"  Namespace 2 ({NAMESPACE2[:16]}...) key count: {len(ns2_keys)}")
print(f"  No cross-contamination: {not set(ns1_keys) & set(ns2_keys)}")

# Registry 1 search doesn't return registry 2 records
nw_results = registry.search_engine.keyword_search("warehouses")
print(f"  'warehouses' not in registry1 results: {all(r['record']['name'] != 'warehouses' for r in nw_results)}")


# ---------------------------------------------------------------------------
# 10. dumps / loads — serialize registry to JSON and restore
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("10. dumps / loads — round-trip serialization")
print(DIVIDER)

from blue_data.registry.registry import Registry
from blue_data.source.json.memory_json_source import MemoryJSONSource

serialized = registry.dumps()
record_count = len(json.loads(serialized))
print(f"  Serialized {record_count} records ({len(serialized):,} chars)")

restored = Registry(store=MemoryJSONSource())
restored.loads(serialized)

orders_record = restored.get_record("orders", "entity", f"/source/{SOURCE_NAME}/database/{SOURCE_DB}/collection/{collection}")
if orders_record:
    print(f"  Restored 'orders' description : {orders_record.get('description', '')}")
    print(f"  Restored 'orders' stats       : {orders_record.get('properties', {}).get('stats', 'n/a')}")

restored_count = len(restored.list_records())
print(f"  Restored total record count   : {restored_count}")
print(f"  Count matches original        : {restored_count == record_count}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Cleanup")
print(DIVIDER)

_cleanup_redis(NAMESPACE,  SCAN_PREFIX,  INDEX_NAME)
_cleanup_redis(NAMESPACE2, SCAN_PREFIX2, INDEX_NAME2)
print("  Redis keys deleted.")

print()
print("Demo complete.")
