import pytest
from blue_data.source.graph.memory_graph_source import MemoryGraphSource


DB = "social"


@pytest.fixture
def graph():
    g = MemoryGraphSource(name="test_graph")
    g.create_database(DB)
    return g


# ===========================================================================
# Nodes
# ===========================================================================

def test_add_and_get_node(graph):
    nid = graph.add_node(DB, "Person", {"name": "Alice"})
    node = graph.get_node(DB, nid)
    assert node["label"] == "Person"
    assert node["properties"]["name"] == "Alice"


def test_add_node_with_explicit_id(graph):
    graph.add_node(DB, "Person", node_id="alice-1")
    assert graph.get_node(DB, "alice-1") is not None


def test_add_node_generates_id(graph):
    nid = graph.add_node(DB, "Company")
    assert nid is not None and len(nid) > 0


def test_get_missing_node_returns_none(graph):
    assert graph.get_node(DB, "ghost") is None


def test_delete_node(graph):
    nid = graph.add_node(DB, "Person")
    graph.delete_node(DB, nid)
    assert graph.get_node(DB, nid) is None


def test_delete_node_removes_connected_edges(graph):
    a = graph.add_node(DB, "Person", node_id="a")
    b = graph.add_node(DB, "Person", node_id="b")
    graph.add_edge(DB, "a", "KNOWS", "b")
    graph.delete_node(DB, "a")
    assert graph.get_neighbors(DB, "b") == []


def test_delete_missing_node_no_error(graph):
    graph.delete_node(DB, "nonexistent")   # should not raise


# ===========================================================================
# Edges
# ===========================================================================

def test_add_and_traverse_edge(graph):
    a = graph.add_node(DB, "Person", node_id="a")
    b = graph.add_node(DB, "Person", node_id="b")
    graph.add_edge(DB, "a", "KNOWS", "b")
    neighbors = graph.get_neighbors(DB, "a", direction="out")
    assert len(neighbors) == 1
    assert neighbors[0]["node"]["id"] == "b"
    assert neighbors[0]["direction"] == "out"


def test_edge_with_properties(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_edge(DB, "a", "KNOWS", "b", properties={"since": 2020})
    neighbors = graph.get_neighbors(DB, "a", direction="out")
    assert neighbors[0]["edge"]["properties"]["since"] == 2020


def test_delete_edge(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_edge(DB, "a", "KNOWS", "b")
    graph.delete_edge(DB, "a", "KNOWS", "b")
    assert graph.get_neighbors(DB, "a") == []


def test_delete_only_matching_edge(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_node(DB, "Person", node_id="c")
    graph.add_edge(DB, "a", "KNOWS", "b")
    graph.add_edge(DB, "a", "KNOWS", "c")
    graph.delete_edge(DB, "a", "KNOWS", "b")
    neighbors = graph.get_neighbors(DB, "a", direction="out")
    assert len(neighbors) == 1
    assert neighbors[0]["node"]["id"] == "c"


# ===========================================================================
# Traversal
# ===========================================================================

def test_get_neighbors_direction_in(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_edge(DB, "a", "FOLLOWS", "b")
    incoming = graph.get_neighbors(DB, "b", direction="in")
    assert len(incoming) == 1
    assert incoming[0]["node"]["id"] == "a"


def test_get_neighbors_direction_both(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_node(DB, "Person", node_id="c")
    graph.add_edge(DB, "a", "KNOWS", "b")
    graph.add_edge(DB, "c", "KNOWS", "a")
    neighbors = graph.get_neighbors(DB, "a", direction="both")
    node_ids = {n["node"]["id"] for n in neighbors}
    assert node_ids == {"b", "c"}


def test_get_neighbors_edge_type_filter(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Person", node_id="b")
    graph.add_node(DB, "Company", node_id="c")
    graph.add_edge(DB, "a", "KNOWS", "b")
    graph.add_edge(DB, "a", "WORKS_AT", "c")
    knows = graph.get_neighbors(DB, "a", edge_type="KNOWS", direction="out")
    assert len(knows) == 1
    assert knows[0]["node"]["id"] == "b"


def test_get_neighbors_empty(graph):
    graph.add_node(DB, "Person", node_id="a")
    assert graph.get_neighbors(DB, "a") == []


# ===========================================================================
# DataSource interface
# ===========================================================================

def test_create_database(graph):
    result = graph.create_database("new_db")
    assert result["status"] == "success"
    assert "new_db" in graph.fetch_databases()


def test_create_database_overwrite(graph):
    graph.add_node(DB, "Person", node_id="x")
    graph.create_database(DB, overwrite=True)
    assert graph.get_node(DB, "x") is None


def test_create_database_no_overwrite_skips(graph):
    graph.add_node(DB, "Person", node_id="x")
    result = graph.create_database(DB, overwrite=False)
    assert result["status"] == "skipped"
    assert graph.get_node(DB, "x") is not None


def test_fetch_databases(graph):
    graph.create_database("db2")
    dbs = graph.fetch_databases()
    assert DB in dbs
    assert "db2" in dbs


def test_fetch_database_collections(graph):
    cols = graph.fetch_database_collections(DB)
    assert cols == [DB]


def test_fetch_database_collection_entities(graph):
    graph.add_node(DB, "Person", {"age": 30})
    graph.add_node(DB, "Person", {"age": 25})
    graph.add_node(DB, "Company", {"size": 100})
    entities = graph.fetch_database_collection_entities(DB, DB)
    assert "Person" in entities
    assert "Company" in entities
    assert "age" in entities["Person"]["contents"]["attributes"]


def test_fetch_database_collection_relations(graph):
    graph.add_node(DB, "Person", node_id="a")
    graph.add_node(DB, "Company", node_id="b")
    graph.add_edge(DB, "a", "WORKS_AT", "b")
    relations = graph.fetch_database_collection_relations(DB, DB)
    assert "WORKS_AT" in relations


def test_fetch_source_stats(graph):
    graph.add_node(DB, "Person")
    graph.add_node(DB, "Person")
    stats = graph.fetch_source_stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 0


def test_fetch_entity_stats(graph):
    graph.add_node(DB, "Person")
    graph.add_node(DB, "Person")
    graph.add_node(DB, "Company")
    stats = graph.fetch_entity_stats(DB, DB, "Person")
    assert stats["row_count"] == 2
