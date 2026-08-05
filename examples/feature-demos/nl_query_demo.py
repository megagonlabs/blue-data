"""
execute_query_nl — natural language querying via the registry.

Shows how DataRegistry.execute_query_nl translates a plain-English question
into a native query (SQL or Cypher) and executes it — all in one call.

Contrast with the LangGraph demos, which wire up the three steps manually:
  search_records → translate_nl_to_native_query → execute_query

Here the registry does all three internally, pulling the schema from the
registry and the LLM callable from the metadata enricher.

Pipeline:
  1. Register SQLite source
  2. Sync + collect stats + Layer 1 enrichment
  3. Wire up LLM via metadata_enricher
  4. execute_query_nl  →  NL → SQL → rows in one call

Run:
    pip install -e lib/
    export OPENAI_API_KEY=sk-...
    python3 examples/feature-demos/nl_query_demo.py
"""

import os
import sqlite3
import tempfile

import openai

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SEP = "-" * 60

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("Set OPENAI_API_KEY to run this demo.")

# ---------------------------------------------------------------------------
# LLM callable — provider-agnostic: any function (str) -> str works
# ---------------------------------------------------------------------------

_client = openai.OpenAI(api_key=api_key)

def llm_fn(prompt: str) -> str:
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

# ---------------------------------------------------------------------------
# 1. Create sample SQLite database
# ---------------------------------------------------------------------------

tmp = tempfile.mkdtemp(prefix="blue-nl-demo-")
conn = sqlite3.connect(os.path.join(tmp, "northwind.db"))
conn.executescript("""
    CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY,
        company_name TEXT,
        country TEXT,
        city TEXT
    );
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id TEXT,
        order_date TEXT,
        freight REAL
    );
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT,
        unit_price REAL,
        units_in_stock INTEGER,
        discontinued INTEGER
    );

    INSERT INTO customers VALUES ('ALFKI', 'Alfreds Futterkiste',   'Germany', 'Berlin');
    INSERT INTO customers VALUES ('ANATR', 'Ana Trujillo',          'Mexico',  'Mexico D.F.');
    INSERT INTO customers VALUES ('AROUT', 'Around the Horn',       'UK',      'London');
    INSERT INTO customers VALUES ('BERGS', 'Berglunds snabbkop',    'Sweden',  'Lulea');
    INSERT INTO customers VALUES ('BOLID', 'Bolido Comidas',        'Spain',   'Madrid');

    INSERT INTO orders VALUES (10248, 'ALFKI', '1996-07-04', 32.38);
    INSERT INTO orders VALUES (10249, 'ANATR', '1996-07-05', 11.61);
    INSERT INTO orders VALUES (10250, 'AROUT', '1996-07-08', 65.83);
    INSERT INTO orders VALUES (10251, 'ALFKI', '1996-07-08', 41.34);
    INSERT INTO orders VALUES (10252, 'BERGS', '1996-07-09', 51.30);
    INSERT INTO orders VALUES (10253, 'BOLID', '1996-07-10', 58.17);

    INSERT INTO products VALUES (1,  'Chai',             18.00,  39, 0);
    INSERT INTO products VALUES (2,  'Chang',            19.00,  17, 0);
    INSERT INTO products VALUES (3,  'Aniseed Syrup',    10.00,  13, 0);
    INSERT INTO products VALUES (4,  'Chef Antons Mix',  22.00,   0, 1);
    INSERT INTO products VALUES (5,  'Grandmas Spread',  25.00, 120, 0);
""")
conn.commit()
conn.close()

# ---------------------------------------------------------------------------
# 2. Register, sync, enrich
# ---------------------------------------------------------------------------

registry = DataRegistry(
    store=MemoryJSONSource(),
    metadata_enricher=MetaData(llm_fn=llm_fn),
)
source = SQLiteDBSource("northwind", properties={
    "connection": {"database_directory": tmp}
})
registry.register_source(source)
registry.sync_source("northwind", recursive=True)
registry.collect_source_stats("northwind", recursive=True)
registry.enrich_source_metadata("northwind", recursive=True)

print("Registry ready — entities:", [
    e["name"] for e in
    registry.list_collection_entities("northwind", "northwind", "public")
])

# ---------------------------------------------------------------------------
# 3. execute_query_nl — one call: NL → SQL → rows
# ---------------------------------------------------------------------------

queries = [
    "How many orders does each customer have?",
    "Which products are discontinued?",
    "What is the average freight cost per country?",
    "List customers from Germany or UK",
]

print()
for nl in queries:
    print(f"{SEP}")
    print(f"  NL:  {nl}")
    rows = registry.execute_query_nl(
        source="northwind",
        query=nl,
        database="northwind",
        collection="public",
    )
    if rows:
        for r in rows[:3]:
            print(f"       {r}")
        if len(rows) > 3:
            print(f"       … {len(rows) - 3} more rows")
    else:
        print("       (no results)")
    print()

print("Demo complete.")
