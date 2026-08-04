"""
LangGraph + blue-data: REST API integration.

A 3-node LangGraph pipeline that talks to blue-data exclusively over HTTP.
No blue-data Python imports on the agent side — only httpx calls to the
running REST API.

  discover  →  translate  →  execute

  1. discover  — GET  /search?q=...&type=entity     find relevant table in registry
  2. translate — GET  /{source}/database/{db}/collection/{col}/entity/{ent}/attributes
                 then LLM NL → SQL using the schema
  3. execute   — POST /{source}/query               run SQL, return rows

Contrast with:
  langgraph_direct_demo.py  — imports blue-data directly (in-process)
  langgraph_mcp_demo.py     — drives blue-data via MCP tools (subprocess)
  langgraph_api_demo.py     — drives blue-data via REST API (network service)  ← this file

Run:
    pip install langgraph langchain-core langchain-openai httpx
    pip install -e lib/ -e platform/api/
    export OPENAI_API_KEY=sk-...
    python3 examples/integration-demos/langgraph_api_demo.py
"""

import json
import os
import sqlite3
import subprocess
import tempfile
import time
from typing import TypedDict

import httpx
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

API_BASE = "http://localhost:8001"


# ---------------------------------------------------------------------------
# Setup: temporary SQLite DB + sources config, then start the API server
# ---------------------------------------------------------------------------

def _setup_demo() -> tuple[str, subprocess.Popen]:
    tmp = tempfile.mkdtemp(prefix="blue-api-demo-")

    db_path = os.path.join(tmp, "shop.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, age INTEGER);
        CREATE TABLE orders    (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL);
        INSERT INTO customers VALUES (1, 'alice@example.com', 30);
        INSERT INTO customers VALUES (2, 'bob@example.com',   25);
        INSERT INTO orders    VALUES (1, 1, 99.9);
        INSERT INTO orders    VALUES (2, 1, 149.0);
        INSERT INTO orders    VALUES (3, 2, 49.5);
    """)
    conn.commit()
    conn.close()

    config = {
        "sources": [
            {
                "type": "sqlite",
                "name": "shop",
                "properties": {"connection": {"database_directory": tmp}},
            }
        ]
    }
    config_path = os.path.join(tmp, "sources.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    env = {
        **os.environ,
        "BLUE_DATA_SOURCES_CONFIG": config_path,
    }
    proc = subprocess.Popen(
        ["uvicorn", "registry_api.main:app", "--port", "8001", "--log-level", "warning"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # wait for the server to be ready
    for _ in range(30):
        try:
            httpx.get(f"{API_BASE}/health", timeout=1).raise_for_status()
            break
        except Exception:
            time.sleep(0.5)

    return tmp, proc


# ---------------------------------------------------------------------------
# Sync the source so its tables appear in the registry
# ---------------------------------------------------------------------------

def _sync_source(source: str) -> None:
    httpx.put(f"{API_BASE}/{source}/sync", params={"recursive": "true"}, timeout=10).raise_for_status()


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def llm_fn(prompt: str) -> str:
    return model.invoke(prompt).content


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class State(TypedDict):
    nl_query:    str
    source_name: str
    database:    str
    collection:  str
    entity_name: str
    schema:      dict
    native_query: str
    results:     list[dict]


# ---------------------------------------------------------------------------
# Node 1: discover
# GET /search?q=...&type=entity — hybrid BM25 + vector search over the registry
# ---------------------------------------------------------------------------

def discover(state: State) -> dict:
    resp = httpx.get(
        f"{API_BASE}/search",
        params={"q": state["nl_query"], "type": "entity"},
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("results", [])
    if not hits:
        return {"source_name": "", "database": "", "collection": "", "entity_name": "", "schema": {}}

    top = hits[0]
    # scope pattern: /source/{source}/database/{db}/collection/{coll}
    parts = top.get("scope", "").strip("/").split("/")
    source_name = parts[1] if len(parts) > 1 else ""
    database    = parts[3] if len(parts) > 3 else ""
    collection  = parts[5] if len(parts) > 5 else "public"
    entity_name = top["name"]

    print(f"[discover] top hit: {entity_name} in {source_name}/{database}/{collection}")
    return {
        "source_name": source_name,
        "database":    database,
        "collection":  collection,
        "entity_name": entity_name,
        "schema":      {},
    }


# ---------------------------------------------------------------------------
# Node 2: translate
# GET /{source}/database/{db}/collection/{col}/entity/{ent}/attributes
# Build a schema string, then NL → SQL via LLM.
# ---------------------------------------------------------------------------

def translate(state: State) -> dict:
    if not state.get("source_name"):
        return {"native_query": ""}

    s, db, col, ent = (
        state["source_name"], state["database"],
        state["collection"], state["entity_name"],
    )

    # fetch attribute list from the REST API
    resp = httpx.get(
        f"{API_BASE}/{s}/database/{db}/collection/{col}/entity/{ent}/attributes",
        timeout=10,
    )
    resp.raise_for_status()
    attributes = resp.json().get("results", [])

    # build a minimal schema string for the LLM prompt
    attr_names = [a["name"] if isinstance(a, dict) else a for a in attributes]
    cols = ", ".join(attr_names) if attr_names else "*"
    schema_str = f"Table: {ent}\nColumns: {cols}"

    prompt = (
        f"You are a SQL expert. Generate a SQLite SELECT query to answer:\n"
        f"  '{state['nl_query']}'\n\n"
        f"Schema:\n{schema_str}\n\n"
        f"Return only the SQL query, no explanation."
    )
    sql = llm_fn(prompt).strip().strip("```sql").strip("```").strip()
    print(f"[translate] SQL: {sql}")
    return {"native_query": sql}


# ---------------------------------------------------------------------------
# Node 3: execute
# POST /{source}/query — run the SQL against the live source
# ---------------------------------------------------------------------------

def execute(state: State) -> dict:
    if not state.get("native_query"):
        return {"results": []}

    resp = httpx.post(
        f"{API_BASE}/{state['source_name']}/query",
        json={"query": state["native_query"], "database": state["database"]},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json().get("results", [])
    print(f"[execute] {len(rows)} rows returned")
    return {"results": rows}


# ---------------------------------------------------------------------------
# Build and run the graph
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


if __name__ == "__main__":
    tmp, proc = _setup_demo()
    try:
        print(f"API server started at {API_BASE}")
        _sync_source("shop")
        print("Registry synced — sources: ['shop']\n")

        nl_query = "Show me all customer orders with their totals"
        print(f"Query: {nl_query}\n")

        result = agent.invoke({
            "nl_query":    nl_query,
            "source_name": "", "database": "", "collection": "",
            "entity_name": "", "schema":   {},
            "native_query": "", "results": [],
        })

        print("\nResults:")
        for row in result["results"]:
            print(" ", row)

    finally:
        proc.terminate()
