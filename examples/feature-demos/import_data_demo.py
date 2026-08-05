"""
import_data — source-to-source data movement.

Shows how blue-data moves rows between registered DataSource objects via
the registry. The source side is a FileSource (CSV files); the target is
a SQLiteDBSource. No manual SQL or pandas code required.

Pipeline:
  1. Write CSV files  →  register as FileSource
  2. Sync FileSource  →  schema appears in registry
  3. Enrich FileSource (Layer 1)  →  semantic types on CSV columns
  4. Create SQLite tables  →  matching schema in target
  5. import_data  →  rows moved source → target
  6. Verify  →  query the SQLite target

Run:
    pip install -e lib/
    python3 examples/feature-demos/import_data_demo.py
"""

import os
import sqlite3
import tempfile

import pandas as pd

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.file.file_source import FileSource
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SEP = "-" * 60


def _print(label, value=None):
    if value is None:
        print(f"\n{SEP}\n{label}\n{SEP}")
    else:
        print(f"  {label}: {value}")


# ---------------------------------------------------------------------------
# 1. Write sample CSV files
# ---------------------------------------------------------------------------

tmp = tempfile.mkdtemp(prefix="blue-import-demo-")
csv_dir = os.path.join(tmp, "csv")
db_dir  = os.path.join(tmp, "db")
os.makedirs(csv_dir)
os.makedirs(db_dir)

pd.DataFrame([
    {"id": 1, "email": "alice@example.com", "country": "US", "age": 30},
    {"id": 2, "email": "bob@example.com",   "country": "UK", "age": 25},
    {"id": 3, "email": "carol@example.com", "country": "US", "age": 35},
]).to_csv(os.path.join(csv_dir, "customers.csv"), index=False)

pd.DataFrame([
    {"id": 1, "customer_id": 1, "amount": 99.90,  "status": "paid"},
    {"id": 2, "customer_id": 1, "amount": 149.00, "status": "paid"},
    {"id": 3, "customer_id": 2, "amount": 49.50,  "status": "pending"},
    {"id": 4, "customer_id": 3, "amount": 200.00, "status": "paid"},
]).to_csv(os.path.join(csv_dir, "orders.csv"), index=False)

_print("1. Source — CSV files")
print(f"  {csv_dir}/customers.csv  (3 rows)")
print(f"  {csv_dir}/orders.csv     (4 rows)")

# ---------------------------------------------------------------------------
# 2. Register sources
# ---------------------------------------------------------------------------

registry = DataRegistry(store=MemoryJSONSource())

file_src   = FileSource("csv_store", directory=csv_dir)
sqlite_src = SQLiteDBSource("sqlite_store", properties={
    "connection": {"database_directory": db_dir}
})

registry.register_source(file_src)
registry.register_source(sqlite_src)

_print("2. Registered sources", registry.list_sources())

# ---------------------------------------------------------------------------
# 3. Sync FileSource — schema into registry
# ---------------------------------------------------------------------------

registry.sync_source("csv_store", recursive=True)

collections = registry.list_database_collections("csv_store", "default")
_print("3. FileSource collections after sync", [c["name"] for c in collections])

# ---------------------------------------------------------------------------
# 4. Create matching tables in SQLite
# ---------------------------------------------------------------------------

conn = sqlite3.connect(os.path.join(db_dir, "shop.db"))
conn.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY, email TEXT, country TEXT, age INTEGER
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT
    );
""")
conn.commit()
conn.close()

_print("4. SQLite tables created", ["customers", "orders"])

# ---------------------------------------------------------------------------
# 6. import_data — FileSource → SQLite
# ---------------------------------------------------------------------------

result_customers = registry.import_data(
    source="csv_store",
    target="sqlite_store",
    database="shop",
    collection="customers",
    entity="customers",
    mode="append",
)

result_orders = registry.import_data(
    source="csv_store",
    target="sqlite_store",
    database="shop",
    collection="orders",
    entity="orders",
    mode="append",
)

_print("5. import_data results")
print(f"  customers → {result_customers}")
print(f"  orders    → {result_orders}")

# ---------------------------------------------------------------------------
# 7. Verify — query the SQLite target
# ---------------------------------------------------------------------------

_print("6. Verify — query SQLite target")

rows = registry.execute_query("sqlite_store", "SELECT * FROM customers", database="shop")
print(f"  customers ({len(rows)} rows):")
for r in rows:
    print(f"    {r}")

rows = registry.execute_query(
    "sqlite_store",
    "SELECT o.id, c.email, o.amount, o.status FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = 'paid'",
    database="shop",
)
print(f"\n  paid orders ({len(rows)} rows):")
for r in rows:
    print(f"    {r}")

# ---------------------------------------------------------------------------
# 8. Overwrite mode — reimport with updated data
# ---------------------------------------------------------------------------

_print("7. Overwrite mode — reload with updated rows")

pd.DataFrame([
    {"id": 1, "email": "alice@example.com", "country": "US", "age": 31},   # age updated
    {"id": 2, "email": "bob@example.com",   "country": "UK", "age": 26},
    {"id": 3, "email": "carol@example.com", "country": "US", "age": 36},
    {"id": 4, "email": "dave@example.com",  "country": "CA", "age": 28},   # new row
]).to_csv(os.path.join(csv_dir, "customers.csv"), index=False)

registry.import_data(
    source="csv_store",
    target="sqlite_store",
    database="shop",
    collection="customers",
    entity="customers",
    mode="overwrite",
)

rows = registry.execute_query("sqlite_store", "SELECT count(*) as n FROM customers", database="shop")
print(f"  row count after overwrite: {rows[0]['n']} (was 3, now 4)")

print("\nDemo complete.")
