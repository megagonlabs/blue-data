"""Regression tests for issue #249.

NEO4JSource.execute_query ignored optional_properties["commit"] and always opened a
READ-mode session unless the library-only key read=False was passed, so a Cypher
write was refused even with commit=True. It also inherited GraphSource's GRAPH.*
op declarations, though it serves only Cypher strings. Server-free: the driver is
mocked and the session's access mode is captured.
"""
from unittest.mock import patch

import pytest

pytest.importorskip("neo4j")
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.graph.neo4j import neo4j_graph_source as mod
from blue_data.source.graph.neo4j.neo4j_graph_source import NEO4JSource

CREATE = "CREATE (n:Probe) RETURN count(n) AS created"


@pytest.fixture
def neo():
    with patch.object(mod, "GraphDatabase"):
        src = NEO4JSource("neo", properties={"connection": {"host": "h", "port": 1}})
    src._edition = "enterprise"  # skip the edition probe; keep the database as given
    return src


def _access_modes(src):
    return [c.kwargs["default_access_mode"] for c in src.connection.session.call_args_list]


def _registry(src):
    reg = DataRegistry()
    reg.register_source(src)
    return reg


@pytest.mark.parametrize("props,mode", [
    (None, "READ"),
    ({"commit": False}, "READ"),
    ({"commit": True}, "WRITE"),
    ({"commit": True, "read": True}, "READ"),  # the explicit library key still wins
])
def test_registry_maps_commit_onto_session_access_mode(neo, props, mode):
    _registry(neo).execute_query("neo", CREATE, database="db", optional_properties=props)
    assert _access_modes(neo) == [mode]


def test_nl_read_only_strips_commit_so_session_stays_read(neo):
    neo.execute_query_nl("count people", database="db",
                         llm_fn=lambda p: "MATCH (n:Person) RETURN count(n)",
                         optional_properties={"commit": True})
    assert _access_modes(neo) == ["READ"]


def test_declares_no_graph_ops():
    assert NEO4JSource._READ_OPS == frozenset()
    assert NEO4JSource._WRITE_OPS == frozenset()


@pytest.mark.parametrize("op", ["GRAPH.GET_NODE", "GRAPH.ADD_NODE"])
def test_registry_refuses_graph_dict_op_as_undeclared(neo, op):
    with pytest.raises(ValueError, match="commit"):
        _registry(neo).execute_query("neo", {"op": op, "id": "x"}, database="db")
    assert not neo.connection.session.called
