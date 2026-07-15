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

Run:
    pip install langgraph langchain-core langchain-openai langchain-mcp-adapters
    pip install -e lib/ -e platform/registry-mcp/
    export OPENAI_API_KEY=sk-...
    python3 examples/langgraph_mcp_demo.py

The registry-mcp server is launched automatically as a subprocess (stdio transport).
No separate terminal needed.
"""

import asyncio

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


async def main():
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Launch registry-mcp as a subprocess (stdio transport — default for MCP servers).
    # The agent receives all MCP tools automatically — no blue-data imports needed.
    async with MultiServerMCPClient({
        "registry": {
            "command": "blue-data-registry-mcp",
            "transport": "stdio",
        }
    }) as client:
        # blue-data MCP tools are now available as LangChain tools
        tools = client.get_tools()
        print(f"Loaded {len(tools)} tools from registry-mcp: {[t.name for t in tools]}\n")

        agent = create_react_agent(model, tools)

        queries = [
            "What data sources are registered?",
            "Find all tables related to customers or orders.",
            "What are the attributes of the orders entity?",
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
