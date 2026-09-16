"""
LangGraph + blue-data: MCP-based integration.

A ReAct agent that uses blue-data's registry-mcp server as tools via
langchain-mcp-adapters. No blue-data-specific code on the LangGraph side —
the agent discovers and calls tools from the running MCP server.

Available registry-mcp tools (auto-discovered):
  search_records         — hybrid BM25 + vector search over the registry
  list_sources           — list registered data sources
  list_source_databases  — list databases in a source
  list_collection_entities — list entities in a collection
  get_entity             — get full entity record with attributes
  sync_source            — sync a source into the registry
  enrich_source          — run semantic enrichment on a source
  execute_query          — run a native query and return rows

Run:
    pip install langgraph langchain-core langchain-openai langchain-mcp-adapters
    pip install -e lib/ -e platform/registry-mcp/
    export OPENAI_API_KEY=sk-...
    python3 examples/langgraph_mcp_demo.py

The registry-mcp server is launched automatically as a subprocess (stdio transport).
No separate terminal needed. A temporary SQLite database is created and passed to
the server via BLUE_DATA_SOURCES_CONFIG so the registry starts with real data.
"""

import asyncio
import json
import os
import sqlite3
import tempfile

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("Set OPENAI_API_KEY to run this demo.")

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


def _setup_demo_db(tmp: str) -> str:
    """Create a sample SQLite database and return the sources config path."""
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

    # Sources config the MCP server reads via BLUE_DATA_SOURCES_CONFIG
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
    return config_path


async def main():
    tmp = tempfile.mkdtemp(prefix="blue-mcp-demo-")
    config_path = _setup_demo_db(tmp)
    print(f"Demo SQLite DB + sources config written to {tmp}\n")

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Launch registry-mcp as a subprocess with the demo sources pre-loaded.
    # BLUE_DATA_SOURCES_CONFIG tells the server which sources to register on startup.
    client = MultiServerMCPClient({
        "registry": {
            "command": "blue-data-registry-mcp",
            "args": [],
            "transport": "stdio",
            "env": {
                **os.environ,
                "BLUE_DATA_SOURCES_CONFIG": config_path,
            },
        }
    })

    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools from registry-mcp: {[t.name for t in tools]}\n")

    agent = create_react_agent(model, tools)

    queries = [
        "What data sources are registered? Then sync the 'shop' source so its tables are in the registry.",
        "Find all tables related to customers or orders.",
        "What are the attributes of the orders entity?",
        "Show me all customer orders with their totals from the shop source.",
    ]

    for query in queries:
        print(f"Query: {query}")
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": query}]
        })
        answer = result["messages"][-1].content
        print(f"Answer: {answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
