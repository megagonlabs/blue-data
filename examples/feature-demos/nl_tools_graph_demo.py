"""
execute_query_nl_tools — tool-based natural language querying for graph sources.

Shows how GraphSource exposes purpose-built graph tools (match_nodes, get_node,
get_neighbors, match_edges) so the LLM can traverse the graph naturally instead
of constructing internal dict ops.

Run:
    pip install -e lib/ anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/feature-demos/nl_tools_graph_demo.py
"""

import os

import anthropic

from blue_data.source.graph.memory_graph_source import MemoryGraphSource

SEP = "-" * 60

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise SystemExit("Set ANTHROPIC_API_KEY to run this demo.")

# ---------------------------------------------------------------------------
# LLM callable — wraps Anthropic tool-use API
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
# 1. Build a small knowledge graph
# ---------------------------------------------------------------------------

src = MemoryGraphSource(name="company_graph")

# People
for node_id, name, role in [
    ("alice",   "Alice",   "Engineer"),
    ("bob",     "Bob",     "Engineer"),
    ("carol",   "Carol",   "Manager"),
    ("dave",    "Dave",    "Director"),
    ("eve",     "Eve",     "Engineer"),
]:
    src.add_node("company", "Person", {"name": name, "role": role}, node_id=node_id)

# Projects
for node_id, title, status in [
    ("proj_alpha", "Project Alpha", "active"),
    ("proj_beta",  "Project Beta",  "completed"),
]:
    src.add_node("company", "Project", {"title": title, "status": status}, node_id=node_id)

# Relationships
src.add_edge("company", "alice", "REPORTS_TO",  "carol")
src.add_edge("company", "bob",   "REPORTS_TO",  "carol")
src.add_edge("company", "eve",   "REPORTS_TO",  "carol")
src.add_edge("company", "carol", "REPORTS_TO",  "dave")
src.add_edge("company", "alice", "WORKS_ON",    "proj_alpha")
src.add_edge("company", "bob",   "WORKS_ON",    "proj_alpha")
src.add_edge("company", "eve",   "WORKS_ON",    "proj_beta")
src.add_edge("company", "alice", "KNOWS",       "bob")
src.add_edge("company", "bob",   "KNOWS",       "eve")

# ---------------------------------------------------------------------------
# 2. Traced llm_fn — prints every tool call and result
# ---------------------------------------------------------------------------

def traced_llm_fn(messages, tools, system=None):
    response = llm_fn(messages, tools, system=system)
    for block in response.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            print(f"    → tool call : {block['name']}({block.get('input', {})})")
    return response


def traced_execute_nl_tool(src, name, tool_input, **kwargs):
    result = src.execute_nl_tool(name, tool_input, **kwargs)
    print(f"    ← tool result: {result}")
    return result


# Monkey-patch execute_nl_tool on the instance for tracing
_orig = src.execute_nl_tool
src.execute_nl_tool = lambda name, tool_input, **kw: traced_execute_nl_tool(src, name, tool_input, **kw)

# ---------------------------------------------------------------------------
# 3. Run NL queries through the tool loop
# ---------------------------------------------------------------------------

queries = [
    "Who are all the engineers in the company?",
    "Who does Alice report to?",
    "Which people are working on Project Alpha?",
    "Who does Carol manage?",
]

print("Graph tool-based NL2Q demo\n")

for nl in queries:
    print(SEP)
    print(f"  Q:  {nl}")
    result = src.execute_query_nl_tools(
        query=nl,
        database="company",
        llm_fn=traced_llm_fn,
    )
    print(f"  A:  ", end="")
    if result:
        for row in result[:5]:
            print(f"      {row}")
        if len(result) > 5:
            print(f"      … {len(result) - 5} more")
    else:
        print("      (no results)")
    print()

print("Demo complete.")
