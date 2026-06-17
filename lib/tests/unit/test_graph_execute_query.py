"""Unit tests for GraphSource.execute_query on MemoryGraphSource and FileGraphSource."""
import pytest

from blue_data.source.graph.memory_graph_source import MemoryGraphSource
from blue_data.source.graph.file_graph_source import FileGraphSource


def _sources(tmp_path):
    return [
        MemoryGraphSource("mem"),
        FileGraphSource("file", directory=str(tmp_path)),
    ]


class TestAddAndGetNode:
    def test_add_node_returns_id(self, tmp_path):
        for src in _sources(tmp_path):
            node_id = src.execute_query(
                {"op": "GRAPH.ADD_NODE", "label": "Person", "properties": {"name": "Alice"}},
                database="db",
            )
            assert isinstance(node_id, str) and node_id

    def test_get_node(self, tmp_path):
        for src in _sources(tmp_path):
            node_id = src.execute_query(
                {"op": "GRAPH.ADD_NODE", "label": "City", "properties": {"name": "NYC"}},
                database="db",
            )
            node = src.execute_query({"op": "GRAPH.GET_NODE", "node_id": node_id}, database="db")
            assert node["label"] == "City"
            assert node["properties"]["name"] == "NYC"

    def test_get_missing_node_returns_none(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query({"op": "GRAPH.GET_NODE", "node_id": "ghost"}, database="db")
            assert result is None

    def test_add_node_with_explicit_id(self, tmp_path):
        for src in _sources(tmp_path):
            node_id = src.execute_query(
                {"op": "GRAPH.ADD_NODE", "label": "Item", "node_id": "item-1"},
                database="db",
            )
            assert node_id == "item-1"


class TestDeleteNode:
    def test_delete_node(self, tmp_path):
        for src in _sources(tmp_path):
            node_id = src.execute_query(
                {"op": "GRAPH.ADD_NODE", "label": "Temp"}, database="db"
            )
            result = src.execute_query({"op": "GRAPH.DELETE_NODE", "node_id": node_id}, database="db")
            assert result is None
            assert src.execute_query({"op": "GRAPH.GET_NODE", "node_id": node_id}, database="db") is None


class TestAddEdgeAndNeighbors:
    def test_add_edge_returns_id(self, tmp_path):
        for src in _sources(tmp_path):
            a = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "A"}, database="db")
            b = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "B"}, database="db")
            edge_id = src.execute_query(
                {"op": "GRAPH.ADD_EDGE", "source_id": a, "edge_type": "KNOWS", "target_id": b},
                database="db",
            )
            assert isinstance(edge_id, str) and edge_id

    def test_get_neighbors(self, tmp_path):
        for src in _sources(tmp_path):
            a = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "A"}, database="db")
            b = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "B"}, database="db")
            src.execute_query(
                {"op": "GRAPH.ADD_EDGE", "source_id": a, "edge_type": "LIKES", "target_id": b},
                database="db",
            )
            neighbors = src.execute_query(
                {"op": "GRAPH.GET_NEIGHBORS", "node_id": a, "direction": "out"},
                database="db",
            )
            assert len(neighbors) == 1
            assert neighbors[0]["node"]["label"] == "B"

    def test_delete_edge(self, tmp_path):
        for src in _sources(tmp_path):
            a = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "A"}, database="db")
            b = src.execute_query({"op": "GRAPH.ADD_NODE", "label": "B"}, database="db")
            src.execute_query(
                {"op": "GRAPH.ADD_EDGE", "source_id": a, "edge_type": "KNOWS", "target_id": b},
                database="db",
            )
            src.execute_query(
                {"op": "GRAPH.DELETE_EDGE", "source_id": a, "edge_type": "KNOWS", "target_id": b},
                database="db",
            )
            neighbors = src.execute_query(
                {"op": "GRAPH.GET_NEIGHBORS", "node_id": a}, database="db"
            )
            assert neighbors == []


class TestErrors:
    def test_non_dict_query_raises(self, tmp_path):
        src = MemoryGraphSource("mem")
        with pytest.raises(ValueError, match="expects query as a dict"):
            src.execute_query("MATCH (n) RETURN n", database="db")

    def test_unknown_op_raises(self, tmp_path):
        src = MemoryGraphSource("mem")
        with pytest.raises(ValueError, match="Unsupported"):
            src.execute_query({"op": "GRAPH.MERGE", "node_id": "x"}, database="db")
