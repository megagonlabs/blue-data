"""Scenario tests for tool-based NL2Q (execute_query_nl_tools).

Uses a scripted mock llm_fn to simulate the LLM tool loop without hitting
any real LLM. Tests cover: tool definitions, tool dispatch, and the full
multi-turn loop for SQL and graph sources.
"""
import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.graph.memory_graph_source import MemoryGraphSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scripted_llm(*responses):
    """Return an llm_fn that plays back *responses* in order."""
    queue = list(responses)

    def llm_fn(messages, tools, system=None):
        return queue.pop(0)

    return llm_fn


def _tool_use_response(tool_id, name, input_dict):
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": input_dict}],
    }


def _text_response(text):
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
    }


# ---------------------------------------------------------------------------
# SQLiteDBSource — tool definitions
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_src(tmp_path):
    src = SQLiteDBSource(
        name="demo_db",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    src.create_database("sales", overwrite=True)
    src.create_database_collection_entity(
        "sales", "public", "orders",
        properties={
            "cols_definition": [
                {"name": "id", "type": "INTEGER"},
                {"name": "customer", "type": "TEXT"},
                {"name": "amount", "type": "REAL"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    for sql in [
        "INSERT INTO orders VALUES (1, 'Alice', 100.0);",
        "INSERT INTO orders VALUES (2, 'Bob', 250.0);",
    ]:
        src.execute_query(sql, database="sales", optional_properties={"commit": True})
    return src


def test_sql_get_nl_tools_has_standard_tools(sqlite_src):
    tools = sqlite_src.get_nl_tools(database="sales", collection="public")
    names = {t["name"] for t in tools}
    assert {"list_databases", "list_collections", "get_schema", "get_metadata", "execute_query"} <= names


def test_sql_execute_query_tool_describes_sql(sqlite_src):
    tools = sqlite_src.get_nl_tools(database="sales")
    eq_tool = next(t for t in tools if t["name"] == "execute_query")
    assert "SQL" in eq_tool["description"]


def test_sql_execute_nl_tool_list_databases(sqlite_src):
    result = sqlite_src.execute_nl_tool("list_databases", {})
    assert "sales" in result


def test_sql_execute_nl_tool_list_collections(sqlite_src):
    result = sqlite_src.execute_nl_tool("list_collections", {"database": "sales"})
    assert "public" in result


def test_sql_execute_nl_tool_get_schema(sqlite_src):
    result = sqlite_src.execute_nl_tool("get_schema", {"database": "sales", "collection": "public"})
    assert "entities" in result


def test_sql_execute_nl_tool_execute_query(sqlite_src):
    result = sqlite_src.execute_nl_tool(
        "execute_query",
        {"query": "SELECT * FROM orders", "database": "sales", "collection": "public"},
    )
    assert len(result) == 2


def test_sql_execute_nl_tool_unknown_raises(sqlite_src):
    with pytest.raises(ValueError, match="Unknown tool"):
        sqlite_src.execute_nl_tool("nonexistent_tool", {})


# ---------------------------------------------------------------------------
# SQLiteDBSource — full tool loop scenarios
# ---------------------------------------------------------------------------

def test_sql_nl_tools_no_llm_fn_returns_empty(sqlite_src):
    result = sqlite_src.execute_query_nl_tools("how many orders?", database="sales", collection="public")
    assert result == []


def test_sql_nl_tools_single_query_then_text(sqlite_src):
    """LLM calls execute_query once, then returns a text answer.
    Should return the query rows (last_query_result)."""
    llm = make_scripted_llm(
        _tool_use_response("t1", "execute_query", {
            "query": "SELECT * FROM orders",
            "database": "sales",
            "collection": "public",
        }),
        _text_response("There are 2 orders totalling 350."),
    )
    result = sqlite_src.execute_query_nl_tools(
        "how many orders are there?",
        database="sales",
        collection="public",
        llm_fn=llm,
    )
    assert len(result) == 2
    assert result[0]["customer"] == "Alice"


def test_sql_nl_tools_multi_turn_explores_then_queries(sqlite_src):
    """LLM calls list_collections, then get_schema, then execute_query, then ends."""
    llm = make_scripted_llm(
        _tool_use_response("t1", "list_collections", {"database": "sales"}),
        _tool_use_response("t2", "get_schema", {"database": "sales", "collection": "public"}),
        _tool_use_response("t3", "execute_query", {
            "query": "SELECT customer, amount FROM orders WHERE amount > 150",
            "database": "sales",
            "collection": "public",
        }),
        _text_response("Bob has an order over 150."),
    )
    result = sqlite_src.execute_query_nl_tools(
        "which customers have orders over 150?",
        database="sales",
        collection="public",
        llm_fn=llm,
    )
    assert len(result) == 1
    assert result[0]["customer"] == "Bob"


def test_sql_nl_tools_text_only_answer(sqlite_src):
    """LLM returns a direct text answer without calling any tool."""
    llm = make_scripted_llm(_text_response("I don't know."))
    result = sqlite_src.execute_query_nl_tools(
        "what is the meaning of life?",
        database="sales",
        llm_fn=llm,
    )
    assert result == [{"answer": "I don't know."}]


# ---------------------------------------------------------------------------
# MemoryGraphSource — tool definitions
# ---------------------------------------------------------------------------

@pytest.fixture
def graph_src():
    src = MemoryGraphSource(name="demo_graph")
    src.add_node("kg", "Person", {"name": "Alice"}, node_id="alice")
    src.add_node("kg", "Person", {"name": "Bob"},   node_id="bob")
    src.add_edge("kg", "alice", "KNOWS", "bob")
    return src


def test_graph_has_no_execute_query_tool(graph_src):
    tools = graph_src.get_nl_tools(database="kg")
    names = {t["name"] for t in tools}
    assert "execute_query" not in names
    assert {"match_nodes", "get_node", "get_neighbors", "match_edges"} <= names


def test_graph_nl_tools_match_nodes(graph_src):
    """LLM calls match_nodes then returns text — result is the matched nodes."""
    llm = make_scripted_llm(
        _tool_use_response("t1", "match_nodes", {"database": "kg", "label": "Person"}),
        _text_response("Found 2 Person nodes."),
    )
    result = graph_src.execute_query_nl_tools(
        "list all people in the graph",
        database="kg",
        llm_fn=llm,
    )
    assert result == [{"answer": "Found 2 Person nodes."}]


def test_graph_nl_tools_get_neighbors(graph_src):
    """LLM calls get_neighbors to traverse from a known node."""
    llm = make_scripted_llm(
        _tool_use_response("t1", "get_neighbors", {"database": "kg", "node_id": "alice"}),
        _text_response("Alice knows Bob."),
    )
    result = graph_src.execute_query_nl_tools(
        "who does Alice know?",
        database="kg",
        llm_fn=llm,
    )
    assert result == [{"answer": "Alice knows Bob."}]
