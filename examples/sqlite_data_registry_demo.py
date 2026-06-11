"""
SQLite DataRegistry end-to-end demo.

Covers the full operational pipeline:
  1. Register a SQLite source and create tables
  2. sync_source — discover schema from live source
  3. collect_source_stats — gather stats at every level
  4. enrich_source — semantic type inference on attributes
  5. Manually register relations and relation attributes
  6. connect_source — lazy reconnect from registry properties
  7. dumps / loads — serialize and restore the full registry
  8. sync_all — multiple sources
  9. create_source_database_collection — registry-only collection creation

Run from lib/:
    PYTHONPATH=src/blue-data python3 ../examples/sqlite_data_registry_demo.py
"""
import hashlib
import json
import math
import os
import sqlite3
import tempfile

from registry.data_registry import DataRegistry
from source.json.memory_json_source import MemoryJSONSource
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from source.vector.memory_vector_source import MemoryVectorSource

DIVIDER = "-" * 60
DIM = 64


def make_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------------------------------------------------------------------------
# Scratch directory — cleaned up automatically
# ---------------------------------------------------------------------------

tmp = tempfile.mkdtemp(prefix="blue-data-demo-")
print(f"Working directory: {tmp}")


# ---------------------------------------------------------------------------
# 1. Register source, create databases and tables
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("1. Register source and create schema")
print(DIVIDER)

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=make_embedding,
    vector_dim=DIM,
    rebuild=True,
    hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
)

source = SQLiteDBSource(
    name="sqlite",
    properties={"connection": {"database_directory": tmp}},
)
registry.register_source(source)
print("Registered sources:", registry.list_sources())

registry.create_source_database("sqlite", "shop", overwrite=True)

registry.create_source_database_collection_entity(
    "sqlite", "shop", "public", "customers",
    creation_properties={
        "cols_definition": [
            {"name": "id", "type": "INTEGER"},
            {"name": "email", "type": "TEXT"},
            {"name": "age", "type": "INTEGER"},
        ],
        "primary_key": ["id"],
    },
    overwrite=True,
)

registry.create_source_database_collection_entity(
    "sqlite", "shop", "public", "orders",
    creation_properties={
        "cols_definition": [
            {"name": "id", "type": "INTEGER"},
            {"name": "customer_id", "type": "INTEGER"},
            {"name": "total", "type": "REAL"},
        ],
        "primary_key": ["id"],
    },
    overwrite=True,
)

for i, (email, age) in enumerate([("alice@example.com", 30), ("bob@example.com", 25), ("carol@example.com", 35)], 1):
    registry.execute_query(
        "sqlite", f"INSERT INTO customers VALUES ({i}, '{email}', {age});",
        database="shop", optional_properties={"commit": True},
    )

for i, (cid, total) in enumerate([(1, 99.9), (1, 149.0), (2, 49.5), (3, 200.0)], 1):
    registry.execute_query(
        "sqlite", f"INSERT INTO orders VALUES ({i}, {cid}, {total});",
        database="shop", optional_properties={"commit": True},
    )

rows = registry.execute_query("sqlite", "SELECT * FROM customers;", database="shop")
print(f"Inserted {len(rows)} customers:", rows)


# ---------------------------------------------------------------------------
# 2. sync_source — discover live schema
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("2. sync_source — discover schema")
print(DIVIDER)

registry.sync_source("sqlite", recursive=True)

dbs = [r["name"] for r in registry.list_source_databases("sqlite")]
print("Databases:", dbs)

collections = [r["name"] for r in registry.list_database_collections("sqlite", "shop")]
print("Collections in 'shop':", collections)

entities = [r["name"] for r in registry.list_collection_entities("sqlite", "shop", "public")]
print("Entities in 'public':", entities)

attrs = [r["name"] for r in registry.list_entity_attributes("sqlite", "shop", "public", "customers")]
print("Attributes of 'customers':", attrs)

schema_json = registry.get_source_database_collection_property("sqlite", "shop", "public", "schema")
print("Schema stored on collection (truncated):", schema_json[:120], "...")


# ---------------------------------------------------------------------------
# 3. Descriptions and properties on hierarchy records
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3. Descriptions and properties")
print(DIVIDER)

registry.set_source_database_description("sqlite", "shop", "E-commerce shop database")
registry.set_source_database_collection_description("sqlite", "shop", "public", "Default public schema")
registry.set_source_database_collection_entity_description("sqlite", "shop", "public", "customers", "Registered customer accounts")
registry.set_source_database_collection_entity_description("sqlite", "shop", "public", "orders", "Customer purchase orders")
registry.set_source_database_collection_entity_attribute_description("sqlite", "shop", "public", "customers", "age", "Customer age in years")

registry.set_source_database_collection_entity_property("sqlite", "shop", "public", "customers", "pii", True)
print("customers.pii:", registry.get_source_database_collection_entity_property("sqlite", "shop", "public", "customers", "pii"))
print("customers.description:", registry.get_source_database_collection_entity_description("sqlite", "shop", "public", "customers"))
print("age.description:", registry.get_source_database_collection_entity_attribute_description("sqlite", "shop", "public", "customers", "age"))


# ---------------------------------------------------------------------------
# 4. collect_source_stats — all levels
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("4. collect_source_stats (recursive)")
print(DIVIDER)

registry.collect_source_stats("sqlite", recursive=True)

db_stats = registry.get_source_database_property("sqlite", "shop", "stats")
print("Database stats:", db_stats)

entity_stats = registry.get_source_database_collection_entity_property("sqlite", "shop", "public", "customers", "stats")
print("Entity stats (customers):", entity_stats)

registry.collect_source_database_collection_entity_attribute_stats("sqlite", "shop", "public", "customers", "age")
attr_stats = registry.get_source_database_collection_entity_attribute_property("sqlite", "shop", "public", "customers", "age", "stats")
print("Attribute stats (age):", attr_stats)


# ---------------------------------------------------------------------------
# 5. enrich_source — semantic type inference
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("5. enrich_source — semantic type inference")
print(DIVIDER)

registry.enrich_source("sqlite")

age_semantics = registry.get_source_database_collection_entity_attribute_property(
    "sqlite", "shop", "public", "customers", "age", "value_semantics"
)
print("age value_semantics:", age_semantics)

email_semantics = registry.get_source_database_collection_entity_attribute_property(
    "sqlite", "shop", "public", "customers", "email", "value_semantics"
)
print("email value_semantics:", email_semantics)


# ---------------------------------------------------------------------------
# 6. Manually register relations and relation attributes
#    (SQLite doesn't enforce FK structure so we register metadata manually)
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("6. Relations and relation attributes")
print(DIVIDER)

registry.register_source_database_collection_relation(
    "sqlite", "shop", "public", "customers_orders",
    description="A customer places many orders",
    properties={"from": "customers", "to": "orders", "cardinality": "one-to-many"},
)

registry.register_source_database_collection_relation_attribute(
    "sqlite", "shop", "public", "customers_orders", "placed_at",
    description="Timestamp when the order was placed",
    properties={"info": {"type": "DATETIME"}},
)

relations = registry.list_collection_relations("sqlite", "shop", "public")
print("Relations:", [r["name"] for r in relations])

rel_props = registry.get_source_database_collection_relation_property("sqlite", "shop", "public", "customers_orders", "cardinality")
print("Relation cardinality:", rel_props)

rel_attrs = registry.get_source_database_collection_relation_attributes("sqlite", "shop", "public", "customers_orders")
print("Relation attributes:", [a["name"] for a in rel_attrs])


# ---------------------------------------------------------------------------
# 7. connect_source — lazy reconnect from stored properties
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("7. connect_source — lazy reconnect")
print(DIVIDER)

# Build a fresh registry with only the source record (no live DataSource object).
# connect_source reads the stored connection properties and instantiates SQLiteDBSource.
lazy_reg = DataRegistry(store=MemoryJSONSource())
lazy_reg.register_record(
    "sqlite",
    "source",
    "/",
    properties={"connection": {"protocol": "sqlite", "database_directory": tmp}},
)

source_obj = lazy_reg.connect_source("sqlite")
print("Lazily connected source type:", type(source_obj).__name__)
print("Source now in registry.sources:", "sqlite" in lazy_reg.sources)

dbs = source_obj.fetch_databases()
print("Databases visible from lazy source:", dbs)


# ---------------------------------------------------------------------------
# 8. dumps / loads — full registry round-trip
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("8. dumps / loads — round-trip serialization")
print(DIVIDER)

serialized = registry.dumps()
print(f"Serialized registry: {len(json.loads(serialized))} records, {len(serialized)} chars")

from registry.registry import Registry
restored = Registry(store=MemoryJSONSource())
restored.loads(serialized)

r = restored.get_record("customers", "entity", "/source/sqlite/database/shop/collection/public")
print("Restored 'customers' description:", r["description"])
print("Restored 'customers' pii property:", r["properties"].get("pii"))
print("Restored total record count:", len(restored.list_records()))


# ---------------------------------------------------------------------------
# 9. sync_all — multiple sources
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("9. sync_all — multiple sources")
print(DIVIDER)

tmp2 = tempfile.mkdtemp(prefix="blue-data-demo2-")

for db_name in ["analytics", "reports"]:
    path = os.path.join(tmp2, f"{db_name}.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT, ts INTEGER)")
    conn.commit()
    conn.close()

multi_reg = DataRegistry(store=MemoryJSONSource())
multi_reg.register_source(SQLiteDBSource("src1", properties={"connection": {"database_directory": tmp}}))
multi_reg.register_source(SQLiteDBSource("src2", properties={"connection": {"database_directory": tmp2}}))

multi_reg.sync_all(recursive=True)

src1_dbs = [r["name"] for r in multi_reg.list_source_databases("src1")]
src2_dbs = [r["name"] for r in multi_reg.list_source_databases("src2")]
print("src1 databases:", src1_dbs)
print("src2 databases:", src2_dbs)

src2_entities = [r["name"] for r in multi_reg.list_collection_entities("src2", "analytics", "public")]
print("src2/analytics entities:", src2_entities)


# ---------------------------------------------------------------------------
# 10. create_source_database_collection — registry-only collection
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("10. create_source_database_collection — registry-only")
print(DIVIDER)

# Manually register the database (no sync) so "public" is not pre-registered.
col_reg = DataRegistry(store=MemoryJSONSource())
col_reg.register_source(SQLiteDBSource("sqlite", properties={"connection": {"database_directory": tmp}}))
col_reg.register_source_database("sqlite", "shop")

result = col_reg.create_source_database_collection("sqlite", "shop", "public")
print("create_source_database_collection result:", result)
print("Collections after create:", [r["name"] for r in col_reg.list_database_collections("sqlite", "shop")])

# Second call with overwrite=False → no-op
result2 = col_reg.create_source_database_collection("sqlite", "shop", "public")
print("Second call (no-op) result:", result2)


# ---------------------------------------------------------------------------
# 11. Search
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("11. search_records — hybrid BM25 + vector")
print(DIVIDER)

results = registry.search_records("customer purchase orders")
print("search_records('customer purchase orders'):")
for r in results[:3]:
    print(f"  [{r.get('_score', 0):.3f}] {r['name']} — {r.get('description', '')[:60]}")

type_results = registry.search_records("orders", type="entity")
print("search_records('orders', type='entity'):", [r["name"] for r in type_results])

print()
print("Demo complete.")
