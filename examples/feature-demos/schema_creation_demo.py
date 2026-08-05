"""
Programmatic schema creation — build a registry without syncing a live source.

Shows create_source_database / create_source_database_collection /
create_source_database_collection_entity in a SQLite context.

Useful when you want to:
  - Pre-declare a schema before data arrives
  - Register a table that doesn't exist yet and create it in one call
  - Document a schema for a system you can't always connect to

Pipeline:
  1. Register SQLite source  (empty database directory)
  2. create_source_database         → creates the SQLite database file
  3. create_source_database_collection  → creates the schema namespace
  4. create_source_database_collection_entity  → CREATE TABLE + registry record
  5. Verify entities visible in registry and queryable via execute_query

Run:
    pip install -e lib/
    python3 examples/feature-demos/schema_creation_demo.py
"""

import tempfile

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SEP = "-" * 60


def _print(label, value=None):
    if value is None:
        print(f"\n{SEP}\n{label}\n{SEP}")
    else:
        print(f"  {label}: {value}")


tmp = tempfile.mkdtemp(prefix="blue-schema-demo-")

registry = DataRegistry(store=MemoryJSONSource())
source = SQLiteDBSource("mydb", properties={"connection": {"database_directory": tmp}})
registry.register_source(source)

_print("1. Registered source — no databases yet")
_print("databases", registry.list_source_databases("mydb"))

# ---------------------------------------------------------------------------
# 2. create_source_database
# ---------------------------------------------------------------------------

result = registry.create_source_database("mydb", "shop")
_print("2. create_source_database('shop')", result)
_print("databases now", registry.list_source_databases("mydb"))

# ---------------------------------------------------------------------------
# 3. create_source_database_collection
# ---------------------------------------------------------------------------

result = registry.create_source_database_collection("mydb", "shop", "public")
_print("3. create_source_database_collection('public')", result)
_print("collections", registry.list_database_collections("mydb", "shop"))

# ---------------------------------------------------------------------------
# 4a. create_source_database_collection_entity — customers
# ---------------------------------------------------------------------------

result = registry.create_source_database_collection_entity(
    source="mydb",
    database="shop",
    collection="public",
    entity="customers",
    creation_properties={
        "cols_definition": [
            {"name": "id",      "type": "INTEGER"},
            {"name": "email",   "type": "TEXT"},
            {"name": "country", "type": "TEXT"},
            {"name": "age",     "type": "INTEGER"},
        ],
        "primary_key": ["id"],
    },
    properties={"description": "Registered customer accounts", "pii": True},
)
_print("4a. create entity 'customers'", result)

# ---------------------------------------------------------------------------
# 4b. create_source_database_collection_entity — orders
# ---------------------------------------------------------------------------

result = registry.create_source_database_collection_entity(
    source="mydb",
    database="shop",
    collection="public",
    entity="orders",
    creation_properties={
        "cols_definition": [
            {"name": "id",          "type": "INTEGER"},
            {"name": "customer_id", "type": "INTEGER"},
            {"name": "total",       "type": "REAL"},
            {"name": "order_date",  "type": "TEXT"},
        ],
        "primary_key": ["id"],
    },
    properties={"description": "Customer purchase orders"},
)
_print("4b. create entity 'orders'", result)

# ---------------------------------------------------------------------------
# 5. Verify registry contents
# ---------------------------------------------------------------------------

_print("5. Entities in registry")
entities = registry.list_collection_entities("mydb", "shop", "public")
for e in entities:
    desc = registry.get_source_database_collection_entity_description("mydb", "shop", "public", e["name"])
    print(f"  {e['name']:<15} description={desc!r}")

pii = registry.get_source_database_collection_entity_property("mydb", "shop", "public", "customers", "pii")
_print("  customers.pii property", pii)

# ---------------------------------------------------------------------------
# 6. Insert rows and query — tables are real SQLite tables
# ---------------------------------------------------------------------------

_print("6. Insert rows and query")

import sqlite3, os
conn = sqlite3.connect(os.path.join(tmp, "shop.db"))
conn.executescript("""
    INSERT INTO customers VALUES (1, 'alice@example.com', 'US', 30);
    INSERT INTO customers VALUES (2, 'bob@example.com',   'UK', 25);
    INSERT INTO orders    VALUES (1, 1, 99.9,  '2024-01-10');
    INSERT INTO orders    VALUES (2, 1, 149.0, '2024-01-15');
    INSERT INTO orders    VALUES (3, 2, 49.5,  '2024-01-20');
""")
conn.commit()
conn.close()

rows = registry.execute_query("mydb", "SELECT * FROM customers", database="shop")
print(f"  customers: {rows}")

rows = registry.execute_query(
    "mydb",
    "SELECT c.email, SUM(o.total) as total_spend FROM orders o JOIN customers c ON o.customer_id = c.id GROUP BY c.id",
    database="shop",
)
print(f"  spend by customer: {rows}")

# ---------------------------------------------------------------------------
# 7. Idempotency — calling create again on existing entity is a no-op
# ---------------------------------------------------------------------------

_print("7. Idempotency — create 'customers' again (no overwrite)")
result = registry.create_source_database_collection_entity(
    source="mydb", database="shop", collection="public", entity="customers",
    creation_properties={"cols_definition": [{"name": "id", "type": "INTEGER"}]},
)
_print("  result (expected None)", result)

print("\nDemo complete.")
