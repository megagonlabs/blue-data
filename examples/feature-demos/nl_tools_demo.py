"""
execute_query_nl_tools — tool-based natural language querying.

Shows how a source's execute_query_nl_tools drives a multi-turn LLM tool loop:
the LLM can call list_databases, list_collections, get_schema, get_metadata,
and execute_query in any order before returning a final answer.

Contrast with nl_query_demo.py, which uses a single one-shot prompt+schema.
Here the LLM explores the source interactively before writing the query.

Run:
    pip install -e lib/ anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/feature-demos/nl_tools_demo.py
"""

import os
import sqlite3
import tempfile

import anthropic

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SEP = "-" * 60

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise SystemExit("Set ANTHROPIC_API_KEY to run this demo.")

# ---------------------------------------------------------------------------
# LLM callable — wraps Anthropic tool-use API
# llm_fn(messages, tools, system=None) -> response dict
# ---------------------------------------------------------------------------

_client = anthropic.Anthropic(api_key=api_key)

def llm_fn(messages, tools, system=None):
    kwargs = dict(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )
    if system:
        kwargs["system"] = system
    resp = _client.messages.create(**kwargs)
    return {
        "stop_reason": resp.stop_reason,
        "content": [block.model_dump() for block in resp.content],
    }

# ---------------------------------------------------------------------------
# 1. Create sample SQLite database
# ---------------------------------------------------------------------------

tmp = tempfile.mkdtemp(prefix="blue-nl-tools-demo-")
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
# 2. Create source (no registry needed for tool-based NL2Q)
# ---------------------------------------------------------------------------

source = SQLiteDBSource("northwind", properties={
    "connection": {"database_directory": tmp}
})

# ---------------------------------------------------------------------------
# 3. execute_query_nl_tools — multi-turn tool loop
# ---------------------------------------------------------------------------

queries = [
    ("northwind", "public", "How many orders does each customer have?"),
    ("northwind", "public", "Which products are discontinued?"),
    ("northwind", "public", "What is the total freight cost for German customers?"),
]

print("Tool-based NL2Q demo — LLM explores the source before querying\n")

for database, collection, nl in queries:
    print(SEP)
    print(f"  Q:  {nl}")
    result = source.execute_query_nl_tools(
        query=nl,
        database=database,
        collection=collection,
        llm_fn=llm_fn,
    )
    if result:
        for row in result[:5]:
            print(f"      {row}")
        if len(result) > 5:
            print(f"      … {len(result) - 5} more rows")
    else:
        print("      (no results)")
    print()

print("Demo complete.")
