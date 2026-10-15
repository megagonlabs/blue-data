"""#118 part B — per-source read-op declaration + loop enforcement, per-call
limit merging, and the write-native-query guard (neo4j Cypher)."""
import pytest

from blue_data.source.source import DataSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


def _tool_use(tid, name, inp):
    return {"stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}


def _end(text="done"):
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}


# ---------- write-native-query guard (base wiring) ----------

class _WriteFlagSource(DataSource):
    def translate_nl_to_native_query(self, query, schema, llm_fn):
        return "WRITE_OP"

    def _is_write_native_query(self, native_query):
        return True

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        return [{"ran": query}]


def test_execute_query_nl_rejects_write_under_read_only():
    s = _WriteFlagSource(name="w")
    with pytest.raises(ValueError, match="read_only=False"):
        s.execute_query_nl("do it", database="db", llm_fn=lambda p: "x")
    # explicit opt-in runs it
    assert s.execute_query_nl("do it", database="db", llm_fn=lambda p: "x", read_only=False) == [{"ran": "WRITE_OP"}]


def test_default_is_write_native_query_is_false():
    assert DataSource(name="d")._is_write_native_query("anything") is False


# ---------- neo4j Cypher write detector (no server) ----------

def test_neo4j_detects_write_cypher():
    pytest.importorskip("neo4j")
    from blue_data.source.graph.neo4j.neo4j_graph_source import NEO4JSource
    s = object.__new__(NEO4JSource)  # skip __init__/connection
    assert s._is_write_native_query("MATCH (n) RETURN n") is False
    assert s._is_write_native_query("MATCH (n:Person) WHERE n.age > 30 RETURN n.name") is False
    for w in ["CREATE (n)", "MATCH (n) DELETE n", "MERGE (a)-[:R]->(b)",
              "MATCH (n) SET n.x = 1", "MATCH (n) REMOVE n.x", "DROP INDEX x"]:
        assert s._is_write_native_query(w) is True, w


# ---------- loop-level per-call limit + allow-list ----------

def test_max_sample_size_caps_sample(tmp_path):
    class _Recording(SQLiteDBSource):
        seen = None

        def fetch_entity_stats(self, database, collection, entity, row_sample_size=100):
            type(self).seen = row_sample_size
            return {"row_samples": [], "row_count": 0}

    s = _Recording(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})
    s.create_database("shop", overwrite=True)
    calls = iter([_tool_use("t1", "get_sample", {"entity": "orders", "sample_size": 9999}), _end()])
    s.execute_query_nl_tools("sample it", database="shop",
                             llm_fn=lambda m, t, system=None: next(calls), max_sample_size=3)
    assert _Recording.seen == 3


def test_off_menu_tool_rejected_under_read_only(tmp_path):
    called = []

    class _Rec(SQLiteDBSource):
        def execute_nl_tool(self, name, tool_input, **kw):
            called.append(name)
            return super().execute_nl_tool(name, tool_input, **kw)

    s = _Rec(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})
    s.create_database("shop", overwrite=True)
    calls = iter([_tool_use("t1", "wipe_everything", {}), _end()])
    s.execute_query_nl_tools("q", database="shop", llm_fn=lambda m, t, system=None: next(calls))
    assert "wipe_everything" not in called  # rejected before dispatch
