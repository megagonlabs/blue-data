"""
Northwind dataset pipeline demo.

Shows the full blue-data pipeline against a realistic multi-table retail
database — register a source, sync the schema, enrich, search the registry
by natural language, and execute a query.

  1. Register  — connect SQLiteDBSource to the Northwind database
  2. Sync      — walk the live schema into the registry
  3. Enrich    — deterministic semantic type inference (no LLM required)
  4. Search    — hybrid BM25 + vector search across registry records
  5. Query     — execute SQL against the registered source

The Northwind schema:
  categories  — product categories
  suppliers   — product suppliers
  customers   — customer accounts
  employees   — sales staff
  products    — product catalog (unit_price, units_in_stock, discontinued)
  orders      — customer orders
  order_details — line items (unit_price, quantity, discount)

Run:
    pip install -e lib/
    python3 examples/northwind_demo.py
"""

import os
import sqlite3
import tempfile
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER  = "=" * 64
SQL_FILE = Path(__file__).parent.parent / "data" / "northwind_sqlite.sql"
DATABASE = "northwind"


# ---------------------------------------------------------------------------
# 1. Register
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("1. Register — connect Northwind SQLite source")
print(DIVIDER)

tmp = tempfile.mkdtemp(prefix="northwind-demo-")
db_path = os.path.join(tmp, f"{DATABASE}.db")
conn = sqlite3.connect(db_path)
conn.executescript(SQL_FILE.read_text())
conn.close()

source = SQLiteDBSource(
    name="northwind",
    properties={"connection": {"database_directory": tmp}},
)

registry = DataRegistry(
    store=MemoryJSONSource(),
    metadata_enricher=MetaData(llm_fn=None),
)
registry.register_source(source)
print(f"  Sources: {registry.list_sources()}")


# ---------------------------------------------------------------------------
# 2. Sync
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("2. Sync — walk live schema into the registry")
print(DIVIDER)

registry.sync_all(recursive=True)

databases   = registry.list_source_databases("northwind")
collections = registry.list_database_collections("northwind", DATABASE)
entities    = registry.list_collection_entities("northwind", DATABASE, "public")

print(f"  Databases:   {[d['name'] for d in databases]}")
print(f"  Collections: {[c['name'] for c in collections]}")
print(f"  Entities:    {[e['name'] for e in entities]}")


# ---------------------------------------------------------------------------
# 3. Enrich
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3. Enrich — deterministic semantic type inference")
print(DIVIDER)

registry.collect_source_stats("northwind", recursive=True)
registry.enrich_source_metadata("northwind", recursive=True, rebuild=False)

interesting = {
    "products":      ["product_id", "unit_price", "units_in_stock", "discontinued"],
    "orders":        ["order_id", "order_date", "ship_country", "freight"],
    "order_details": ["unit_price", "quantity", "discount"],
    "employees":     ["employee_id", "hire_date", "title"],
}

for entity, attrs in interesting.items():
    print(f"\n  {entity}")
    for attr in attrs:
        vsi  = registry.get_source_database_collection_entity_attribute_property(
                   "northwind", DATABASE, "public", entity, attr, "value_semantics") or {}
        role = registry.get_source_database_collection_entity_attribute_property(
                   "northwind", DATABASE, "public", entity, attr, "semantic_role") or {}
        print(f"    {attr:<22} {vsi.get('semantic_type','—'):<22} {role.get('primary_role','—')}")

# Process semantics on orders
ps = registry.get_source_database_collection_entity_property(
    "northwind", DATABASE, "public", "orders", "process_semantics"
)
if ps:
    print(f"\n  orders process semantics:")
    print(f"    row_semantics = {ps.get('row_semantics')}")
    print(f"    event_time    = {ps.get('event_time')}")


# ---------------------------------------------------------------------------
# 4. Search
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("4. Search — hybrid BM25 + vector search over the registry")
print(DIVIDER)

queries = [
    ("revenue and pricing",      "attribute"),
    ("discontinued products",    "attribute"),
    ("customer and order dates", "entity"),
    ("employee hire date",       "attribute"),
    ("stock and inventory",      "attribute"),
]

for query, record_type in queries:
    hits = registry.search_records(query, type=record_type)
    print(f"\n  '{query}'  [{record_type}]")
    if not hits:
        print("    (no results — add a VectorSource + embedding_fn to enable hybrid search)")
        continue
    for h in hits[:3]:
        scope = h.get("scope", "")
        entity_part = scope.split("/entity/")[-1] if "/entity/" in scope else ""
        label = f"{entity_part}.{h['name']}" if entity_part else h["name"]
        print(f"    {label} ({h.get('_score', 0):.2f})")


# ---------------------------------------------------------------------------
# 5. Query
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("5. Query — execute SQL against the registered source")
print(DIVIDER)

queries_sql = [
    (
        "Top 5 products by unit price",
        "SELECT product_name, unit_price, units_in_stock "
        "FROM products ORDER BY unit_price DESC LIMIT 5",
    ),
    (
        "Orders per country",
        "SELECT ship_country, COUNT(*) as order_count "
        "FROM orders GROUP BY ship_country ORDER BY order_count DESC LIMIT 5",
    ),
    (
        "Revenue by category",
        "SELECT c.category_name, "
        "  ROUND(SUM(od.unit_price * od.quantity * (1 - od.discount)), 2) AS revenue "
        "FROM order_details od "
        "JOIN products p ON od.product_id = p.product_id "
        "JOIN categories c ON p.category_id = c.category_id "
        "GROUP BY c.category_name ORDER BY revenue DESC",
    ),
    (
        "Discontinued products still in stock",
        "SELECT product_name, units_in_stock, unit_price "
        "FROM products WHERE discontinued = 1 AND units_in_stock > 0",
    ),
]

for title, sql in queries_sql:
    rows = registry.execute_query(
        "northwind", sql, database=DATABASE, collection="public"
    )
    print(f"\n  {title}")
    print(f"  SQL: {sql[:80]}{'...' if len(sql) > 80 else ''}")
    for row in rows[:5]:
        print(f"    {row}")

print()
print("Demo complete.")
