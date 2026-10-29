"""Regression tests for issue #206.

Only SQLSource gated writes; Mongo/Redis-JSON/graph/vector/stream mutations ran on
REST /query and MCP execute_query with writes disabled. DataRegistry.execute_query
now refuses a write op (per each source's _WRITE_OPS) unless commit is set.
"""
import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.source import DataSource


class _StubWriteSource(DataSource):
    _WRITE_OPS = frozenset({"DELETE_MANY"})

    def __init__(self, name, properties=None):
        super().__init__(name, properties)
        self.calls = []

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        self.calls.append(query)
        return [{"ok": 1}]


def _reg():
    reg = DataRegistry()
    reg.register_source(_StubWriteSource("s"))
    return reg


@pytest.mark.parametrize("query", [{"op": "DELETE_MANY", "filter": {}}, '{"op":"DELETE_MANY"}'])
def test_registry_refuses_write_op_without_commit(query):
    reg = _reg()
    with pytest.raises(ValueError, match="commit"):
        reg.execute_query("s", query, database="demo", collection="people")
    assert reg.get_source("s").calls == []  # refused before reaching the source


def test_registry_allows_read_op():
    reg = _reg()
    reg.execute_query("s", {"op": "FIND", "filter": {}})
    assert reg.get_source("s").calls == [{"op": "FIND", "filter": {}}]


def test_registry_allows_write_op_with_commit():
    reg = _reg()
    reg.execute_query("s", {"op": "DELETE_MANY"}, optional_properties={"commit": True})
    assert reg.get_source("s").calls == [{"op": "DELETE_MANY"}]


def test_plain_sql_string_is_not_classified_as_a_write_here():
    # SQL guards its own string queries inside SQLSource; the registry classifier
    # only gates dict/JSON ops, so a SQL string must pass through unchanged.
    reg = _reg()
    reg.execute_query("s", "DELETE FROM t")
    assert reg.get_source("s").calls == ["DELETE FROM t"]


def test_each_source_declares_its_write_ops():
    from blue_data.source.graph.graph_source import GraphSource
    from blue_data.source.vector.vector_source import VectorSource
    from blue_data.source.stream.stream_source import StreamSource

    assert {"GRAPH.ADD_NODE", "GRAPH.DELETE_NODE", "GRAPH.UPDATE_EDGE"} <= GraphSource._WRITE_OPS
    assert "GRAPH.GET_NODE" not in GraphSource._WRITE_OPS
    assert {"VECTOR.UPSERT", "VECTOR.DELETE"} <= VectorSource._WRITE_OPS
    assert "VECTOR.KNN" not in VectorSource._WRITE_OPS
    assert "STREAM.PUBLISH" in StreamSource._WRITE_OPS
    assert "STREAM.CONSUME" not in StreamSource._WRITE_OPS

    pytest.importorskip("pymongo")
    from blue_data.source.json.mongodb.mongodb_json_source import MongoDBSource
    assert {"DELETE_MANY", "INSERT_ONE"} <= MongoDBSource._WRITE_OPS
    assert "FIND" not in MongoDBSource._WRITE_OPS

    pytest.importorskip("redis")
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    assert {"JSON.SET", "JSON.DEL"} <= RedisJSONSource._WRITE_OPS
    assert "JSON.GET" not in RedisJSONSource._WRITE_OPS
