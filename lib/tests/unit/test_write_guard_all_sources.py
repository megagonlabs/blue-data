"""Regression tests for issues #206 and #237.

Only SQLSource gated writes; Mongo/Redis-JSON/graph/vector/stream mutations ran on
REST /query and MCP execute_query with writes disabled (#206). The guard then let
through every op a source did not list in _WRITE_OPS, so JSON SET/DEL wrote on
read-only paths (#237). DataRegistry.execute_query is now deny-by-default: without
commit only an op in the source's _READ_OPS runs.
"""
import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.source import DataSource


class _StubWriteSource(DataSource):
    _READ_OPS = frozenset({"FIND"})
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


@pytest.mark.parametrize("query", [
    {"op": "UPDATE_MANY", "filter": {}},
    '{"op": "update_many"}',
    {"filter": {}},
    {"op": 7},
    {"op": ["FIND"]},
])
def test_registry_refuses_undeclared_op_without_commit(query):
    reg = _reg()
    with pytest.raises(ValueError, match="commit"):
        reg.execute_query("s", query)
    assert reg.get_source("s").calls == []


@pytest.mark.parametrize("query", [{"op": "FIND", "filter": {}}, '{"op": "find"}'])
def test_registry_allows_declared_read_op(query):
    reg = _reg()
    reg.execute_query("s", query)
    assert reg.get_source("s").calls == [query]


@pytest.mark.parametrize("op", ["DELETE_MANY", "UPDATE_MANY"])
def test_registry_allows_write_or_undeclared_op_with_commit(op):
    reg = _reg()
    reg.execute_query("s", {"op": op}, optional_properties={"commit": True})
    assert reg.get_source("s").calls == [{"op": op}]


def test_plain_sql_string_is_not_classified_as_a_write_here():
    # SQL guards its own string queries inside SQLSource; the registry classifier
    # only gates dict/JSON ops, so a SQL string must pass through unchanged.
    reg = _reg()
    reg.execute_query("s", "DELETE FROM t")
    assert reg.get_source("s").calls == ["DELETE FROM t"]


def test_source_declaring_nothing_is_refused_every_dict_op():
    class Bare(DataSource):
        def execute_query(self, query, database=None, collection=None, optional_properties=None):
            raise AssertionError("must not be reached")

    reg = DataRegistry()
    reg.register_source(Bare("b"))
    with pytest.raises(ValueError, match="commit"):
        reg.execute_query("b", {"op": "ANYTHING"})


def test_memory_json_set_and_del_refused_without_commit():
    """#237 reproduction: JSON.SET/JSON.DEL on MemoryJSONSource ran on a read."""
    reg = DataRegistry()
    reg.register_source(MemoryJSONSource("mem"))
    for q in ({"op": "JSON.SET", "path": "flag", "value": "placeholder"},
              {"op": "SET", "path": "flag", "value": "placeholder"},
              {"op": "JSON.DEL", "path": "flag"}):
        with pytest.raises(ValueError, match="commit"):
            reg.execute_query("mem", q)
    assert reg.execute_query("mem", {"op": "JSON.GET"}) == {}

    reg.execute_query("mem", {"op": "JSON.SET", "path": "flag", "value": 1},
                      optional_properties={"commit": True})
    assert reg.execute_query("mem", {"op": "GET", "path": "flag"}) == 1


# Every dict op each built-in source's execute_query dispatches. A source must
# declare each of these in exactly one of _READ_OPS / _WRITE_OPS (#237). None is
# the op-less dict some sources accept.
def _served_ops():
    from blue_data.source.file.file_source import FileSource
    from blue_data.source.graph.graph_source import GraphSource
    from blue_data.source.json.json_source import JSONSource
    from blue_data.source.network.network_source import NetworkSource
    from blue_data.source.sql.sql_source import SQLSource
    from blue_data.source.stream.stream_source import StreamSource
    from blue_data.source.vector.vector_source import VectorSource

    served = {
        JSONSource: ({"GET", "JSON.GET"}, {"SET", "JSON.SET", "DEL", "DELETE", "JSON.DEL"}),
        GraphSource: (
            {"GRAPH.GET_NODE", "GRAPH.MATCH_NODE", "GRAPH.MATCH_EDGE", "GRAPH.GET_NEIGHBORS"},
            {"GRAPH.ADD_NODE", "GRAPH.ADD_EDGE", "GRAPH.UPDATE_NODE", "GRAPH.UPDATE_EDGE",
             "GRAPH.DELETE_NODE", "GRAPH.DELETE_EDGE"},
        ),
        VectorSource: (
            {"VECTOR.KNN", "VECTOR.LIST_IDS"},
            {"VECTOR.CREATE_INDEX", "VECTOR.UPSERT", "VECTOR.DELETE", "VECTOR.DELETE_BY_PREFIX"},
        ),
        StreamSource: (
            {"STREAM.CONSUME"},
            {"STREAM.PUBLISH", "STREAM.ACKNOWLEDGE", "STREAM.CREATE", "STREAM.DELETE"},
        ),
        NetworkSource: (
            {"NETWORK.FETCH_NODES", "NETWORK.FETCH_EDGES", "NETWORK.INFER"}, {"NETWORK.CREATE"},
        ),
        FileSource: ({"FILE.READ", "FILE.FIND", None}, set()),
        SQLSource: ({"SQL.QUERY", "SQL.FETCH_ALL"}, set()),
    }
    for module, cls_name, ops in (
        ("blue_data.source.json.mongodb.mongodb_json_source", "MongoDBSource",
         ({"FIND", "COUNT", "DISTINCT", "AGGREGATE"}, {"INSERT_ONE", "DELETE_MANY"})),
        ("blue_data.source.json.redis.redis_json_source", "RedisJSONSource",
         ({"JSON.GET"}, {"JSON.SET", "JSON.DEL"})),
        ("blue_data.source.network.bn.bayesian_network_source", "BayesianNetworkSource",
         ({None}, set())),
    ):
        try:
            mod = __import__(module, fromlist=[cls_name])
        except ImportError:
            continue
        served[getattr(mod, cls_name)] = ops
    return served


@pytest.mark.parametrize("cls,ops", list(_served_ops().items()), ids=lambda v: getattr(v, "__name__", ""))
def test_each_source_declares_every_op_it_serves_exactly_once(cls, ops):
    reads, writes = ops
    assert not cls._READ_OPS & cls._WRITE_OPS
    assert reads <= cls._READ_OPS, f"{cls.__name__} must declare its reads in _READ_OPS"
    assert writes <= cls._WRITE_OPS, f"{cls.__name__} must declare its writes in _WRITE_OPS"
