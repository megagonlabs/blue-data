"""
export_data — export rows from a registered DataSource to a file.

Shows how blue-data exports table data from a SQLiteDBSource directly
to CSV, JSON, and JSONL files via the registry — no manual pandas or
SQL boilerplate required.

Pipeline:
  1. Create a SQLite database with sample data
  2. Register it as a DataSource
  3. export_data → CSV (format inferred from extension)
  4. export_data → JSON (format inferred from extension)
  5. export_data with a filter → JSONL (filtered rows only)

Run:
    pip install -e lib/
    python3 examples/feature-demos/export_data_demo.py
"""

import os
import sqlite3
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


# ---------------------------------------------------------------------------
# 1. Create a SQLite database with sample data
# ---------------------------------------------------------------------------

tmp    = tempfile.mkdtemp(prefix="blue-export-demo-")
db_dir = os.path.join(tmp, "db")
out_dir = os.path.join(tmp, "exports")
os.makedirs(db_dir)
os.makedirs(out_dir)

db_path = os.path.join(db_dir, "shop.db")
conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY, email TEXT, country TEXT, age INTEGER
    );
    INSERT INTO customers VALUES
        (1, 'alice@example.com', 'US', 30),
        (2, 'bob@example.com',   'UK', 25),
        (3, 'carol@example.com', 'US', 35),
        (4, 'dave@example.com',  'CA', 28);

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT
    );
    INSERT INTO orders VALUES
        (1, 1, 99.90,  'paid'),
        (2, 1, 149.00, 'paid'),
        (3, 2, 49.50,  'pending'),
        (4, 3, 200.00, 'paid');
""")
conn.commit()
conn.close()

_print("1. SQLite database created", db_path)

# ---------------------------------------------------------------------------
# 2. Register source
# ---------------------------------------------------------------------------

registry = DataRegistry(store=MemoryJSONSource())

sqlite_src = SQLiteDBSource("shop_db", properties={
    "connection": {"database_directory": db_dir}
})
registry.register_source(sqlite_src)

_print("2. Registered sources", registry.list_sources())

# ---------------------------------------------------------------------------
# 3. Export customers table → CSV (format inferred from .csv extension)
# ---------------------------------------------------------------------------

_print("3. Export customers → CSV")

csv_path = os.path.join(out_dir, "customers.csv")
result = registry.export_data(
    source="shop_db",
    path=csv_path,
    database="shop",
    collection="customers",
)
_print("result", result)

import csv
with open(csv_path) as f:
    rows = list(csv.DictReader(f))
print(f"  preview ({len(rows)} rows):")
for r in rows:
    print(f"    {r}")

# ---------------------------------------------------------------------------
# 4. Export orders table → JSON (format inferred from .json extension)
# ---------------------------------------------------------------------------

_print("4. Export orders → JSON")

json_path = os.path.join(out_dir, "orders.json")
result = registry.export_data(
    source="shop_db",
    path=json_path,
    database="shop",
    collection="orders",
)
_print("result", result)

import json
with open(json_path) as f:
    rows = json.load(f)
print(f"  preview ({len(rows)} rows):")
for r in rows:
    print(f"    {r}")

# ---------------------------------------------------------------------------
# 5. Filtered export — paid orders only → JSONL
# ---------------------------------------------------------------------------

_print("5. Filtered export — paid orders → JSONL")

jsonl_path = os.path.join(out_dir, "paid_orders.jsonl")
result = registry.export_data(
    source="shop_db",
    path=jsonl_path,
    database="shop",
    collection="orders",
    query="SELECT * FROM orders WHERE status = 'paid'",
)
_print("result", result)

with open(jsonl_path) as f:
    lines = [json.loads(l) for l in f if l.strip()]
print(f"  preview ({len(lines)} rows):")
for r in lines:
    print(f"    {r}")

print("\nDemo complete.")
