"""
LangGraph + blue-data: Direct Python API integration.

A 3-node LangGraph pipeline that uses blue-data primitives directly:

  discover  →  translate  →  execute

  1. discover  — DataRegistry.search_records()             find relevant data in the registry
  2. translate — DataSource.translate_nl_to_native_query() NL → SQL
  3. execute   — DataSource.execute_query()                run the SQL and return rows

Run:
    pip install langgraph langchain-core langchain-openai
    pip install -e lib/
    export OPENAI_API_KEY=sk-...
    python3 examples/langgraph_direct_demo.py
"""

import hashlib
import math
import os
import sqlite3
import tempfile
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

# ---------------------------------------------------------------------------
# Deterministic embeddings — no API call needed for the registry index
# ---------------------------------------------------------------------------

DIM = 64


def _embed(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------------------------------------------------------------------------
# Setup: SQLite source with sample data + registry
# ---------------------------------------------------------------------------

tmp = tempfile.mkdtemp(prefix="blue-langgraph-")

db_path = os.path.join(tmp, "shop.db")
conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, age INTEGER);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL);
    INSERT INTO customers VALUES (1, 'alice@example.com', 30);
    INSERT INTO customers VALUES (2, 'bob@example.com', 25);
    INSERT INTO orders VALUES (1, 1, 99.9);
    INSERT INTO orders VALUES (2, 1, 149.0);
    INSERT INTO orders VALUES (3, 2, 49.5);
""")
conn.commit()
conn.close()

source = SQLiteDBSource("shop", properties={"connection": {"database_directory": tmp}})

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=_embed,
    vector_dim=DIM,
    rebuild=True,
    hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
)
registry.register_source(source)
# sync_source walks the live source and registers databases, collections, entities
registry.sync_source("shop", recursive=True)

print("Registry ready — sources:", registry.list_sources())

# ---------------------------------------------------------------------------
# LLM — any OpenAI-compatible model
# ---------------------------------------------------------------------------

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def llm_fn(prompt: str) -> str:
    return model.invoke(prompt).content


# ---------------------------------------------------------------------------
# Agent state passed between nodes
# ---------------------------------------------------------------------------


class State(TypedDict):
    nl_query: str        # natural language question from the user
    source_name: str     # resolved by discover
    database: str        # resolved by discover
    collection: str      # resolved by discover
    schema: dict         # built by discover for the translate step
    native_query: str    # SQL produced by translate
    results: list[dict]  # rows returned by execute


# ---------------------------------------------------------------------------
# Node 1: discover
# Uses DataRegistry.search_records() to find the most relevant entity,
# then builds a schema dict for the translate step.
# ---------------------------------------------------------------------------


def discover(state: State) -> dict:
    # blue-data primitive: hybrid BM25 + vector search over the registry
    hits = registry.search_records(state["nl_query"], type="entity")
    if not hits:
        return {"source_name": "", "database": "", "collection": "", "schema": {}}

    top = hits[0]
    # scope pattern: /source/{source}/database/{db}/collection/{coll}
    parts = top.get("scope", "").strip("/").split("/")
    source_name = parts[1] if len(parts) > 1 else ""
    database    = parts[3] if len(parts) > 3 else ""
    collection  = parts[5] if len(parts) > 5 else "public"

    # blue-data primitive: build schema dict for translate_nl_to_native_query
    schema = registry.build_schema_for_nl(source_name, database, collection)

    print(f"[discover] top hit: {top['name']} in {source_name}/{database}/{collection}")
    return {
        "source_name": source_name,
        "database": database,
        "collection": collection,
        "schema": schema,
    }


# ---------------------------------------------------------------------------
# Node 2: translate
# Uses DataSource.translate_nl_to_native_query() — NL → SQL.
# Internally calls _format_schema_for_nl, _build_nl_prompt, llm_fn,
# and _extract_native_query on the source.
# ---------------------------------------------------------------------------


def translate(state: State) -> dict:
    if not state.get("source_name"):
        return {"native_query": ""}

    src = registry.sources[state["source_name"]]

    # blue-data primitive: NL → SQL via the three hook methods on DataSource
    native_query = src.translate_nl_to_native_query(
        state["nl_query"],
        state["schema"],
        llm_fn,
    )
    print(f"[translate] SQL: {native_query}")
    return {"native_query": native_query or ""}


# ---------------------------------------------------------------------------
# Node 3: execute
# Uses DataSource.execute_query() — run the SQL and return rows.
# ---------------------------------------------------------------------------


def execute(state: State) -> dict:
    if not state.get("native_query"):
        return {"results": []}

    src = registry.sources[state["source_name"]]

    # blue-data primitive: execute the native query against the source
    rows = src.execute_query(state["native_query"], database=state["database"])
    print(f"[execute] {len(rows)} rows returned")
    return {"results": rows}


# ---------------------------------------------------------------------------
# Build the graph: discover → translate → execute → END
# ---------------------------------------------------------------------------

graph = StateGraph(State)
graph.add_node("discover", discover)
graph.add_node("translate", translate)
graph.add_node("execute", execute)

graph.set_entry_point("discover")
graph.add_edge("discover", "translate")
graph.add_edge("translate", "execute")
graph.add_edge("execute", END)

agent = graph.compile()

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

nl_query = "Show me all customer orders with their totals"
print(f"\nQuery: {nl_query}\n")

result = agent.invoke({
    "nl_query": nl_query,
    "source_name": "", "database": "", "collection": "",
    "schema": {}, "native_query": "", "results": [],
})

print("\nResults:")
for row in result["results"]:
    print(" ", row)
