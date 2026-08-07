"""Unit tests for FileGraphSource — DataSource interface and persistence.

Transaction and execute_query behaviour is tested separately in
test_graph_transactions.py and test_graph_execute_query.py.
These tests focus on the file-backed DataSource methods: create_database,
fetch_databases, stats, and schema introspection.
"""
import json
import os

import pytest

from blue_data.source.graph.file_graph_source import FileGraphSource


DB = "social"


@pytest.fixture
def src(tmp_path):
    return FileGraphSource(name="fg", directory=str(tmp_path))


def _populated(tmp_path) -> FileGraphSource:
    """Return a fresh FileGraphSource with one Person and one Company connected."""
    s = FileGraphSource(name="fg", directory=str(tmp_path))
    s.create_database(DB)
    a = s.add_node(DB, "Person", {"name": "Alice", "age": 30})
    b = s.add_node(DB, "Company", {"name": "Acme"})
    s.add_edge(DB, a, "WORKS_AT", b, properties={"since": 2020})
    return s


# ===========================================================================
# create_database
# ===========================================================================

class TestCreateDatabase:
    def test_create_writes_json_file(self, src, tmp_path):
        src.create_database(DB)
        assert (tmp_path / f"{DB}.json").exists()

    def test_create_returns_success(self, src):
        result = src.create_database(DB)
        assert result["status"] == "success"

    def test_create_skips_existing_without_overwrite(self, src):
        src.create_database(DB)
        src.add_node(DB, "Person", node_id="x")
        result = src.create_database(DB, overwrite=False)
        assert result["status"] == "skipped"

    def test_create_overwrites_existing_data(self, src):
        src.create_database(DB)
        src.add_node(DB, "Person", node_id="x")
        src.create_database(DB, overwrite=True)
        fresh = FileGraphSource(name="fg2", directory=src._directory)
        assert fresh.get_node(DB, "x") is None

    def test_overwrite_resets_file_contents(self, src, tmp_path):
        src.create_database(DB)
        src.add_node(DB, "Person")
        src.create_database(DB, overwrite=True)
        data = json.loads((tmp_path / f"{DB}.json").read_text())
        assert data["nodes"] == {}
        assert data["edges"] == {}


# ===========================================================================
# fetch_databases
# ===========================================================================

class TestFetchDatabases:
    def test_empty_directory_returns_no_databases(self, src):
        assert src.fetch_databases() == []

    def test_returns_created_database(self, src):
        src.create_database(DB)
        assert DB in src.fetch_databases()

    def test_returns_multiple_databases(self, src):
        src.create_database("db1")
        src.create_database("db2")
        dbs = src.fetch_databases()
        assert "db1" in dbs
        assert "db2" in dbs

    def test_cross_instance_visibility(self, src, tmp_path):
        src.create_database(DB)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        assert DB in fresh.fetch_databases()

    def test_txn_files_not_listed_as_databases(self, src):
        src.create_database(DB)
        tid = src.begin_transaction(DB)
        # .txn sidecars must not appear as databases
        dbs = src.fetch_databases()
        assert all(not d.endswith(".txn") for d in dbs)
        src.rollback_transaction(tid)


# ===========================================================================
# Persistence: data survives process restart
# ===========================================================================

class TestPersistence:
    def test_nodes_survive_reload(self, tmp_path):
        s1 = _populated(tmp_path)
        s2 = FileGraphSource(name="fg2", directory=str(tmp_path))
        nodes = s2.match_nodes(DB, label="Person")
        assert len(nodes) == 1
        assert nodes[0]["properties"]["name"] == "Alice"

    def test_edges_survive_reload(self, tmp_path):
        s1 = _populated(tmp_path)
        s2 = FileGraphSource(name="fg2", directory=str(tmp_path))
        edges = s2.match_edges(DB, edge_type="WORKS_AT")
        assert len(edges) == 1

    def test_delete_node_persisted(self, tmp_path):
        s1 = _populated(tmp_path)
        nid = s1.match_nodes(DB, label="Person")[0]["id"]
        s1.delete_node(DB, nid)
        s2 = FileGraphSource(name="fg2", directory=str(tmp_path))
        assert s2.get_node(DB, nid) is None

    def test_update_node_persisted(self, tmp_path):
        s1 = _populated(tmp_path)
        nid = s1.match_nodes(DB, label="Person")[0]["id"]
        s1.update_node(DB, nid, {"age": 99})
        s2 = FileGraphSource(name="fg2", directory=str(tmp_path))
        assert s2.get_node(DB, nid)["properties"]["age"] == 99


# ===========================================================================
# fetch_source_stats
# ===========================================================================

class TestFetchSourceStats:
    def test_empty_source(self, src):
        stats = src.fetch_source_stats()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_counts_across_databases(self, tmp_path):
        s = _populated(tmp_path)
        s.create_database("db2")
        s.add_node("db2", "Item")
        stats = s.fetch_source_stats()
        assert stats["total_nodes"] == 3  # Alice + Company + Item
        assert stats["total_edges"] == 1

    def test_cross_instance_stats(self, tmp_path):
        _populated(tmp_path)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        stats = fresh.fetch_source_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1


# ===========================================================================
# fetch_database_metadata / fetch_database_schema
# ===========================================================================

class TestDatabaseIntrospection:
    def test_metadata_node_edge_count(self, tmp_path):
        s = _populated(tmp_path)
        meta = s.fetch_database_metadata(DB)
        assert meta["node_count"] == 2
        assert meta["edge_count"] == 1

    def test_metadata_cross_instance(self, tmp_path):
        _populated(tmp_path)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        meta = fresh.fetch_database_metadata(DB)
        assert meta["node_count"] == 2

    def test_schema_returns_labels_and_edge_types(self, tmp_path):
        s = _populated(tmp_path)
        schema = s.fetch_database_schema(DB)
        assert "Person" in schema["node_labels"]
        assert "Company" in schema["node_labels"]
        assert "WORKS_AT" in schema["edge_types"]


# ===========================================================================
# fetch_database_collection_entities / relations
# ===========================================================================

class TestSchemaIntrospection:
    def test_entities_returned_by_label(self, tmp_path):
        s = _populated(tmp_path)
        entities = s.fetch_database_collection_entities(DB, DB)
        assert "Person" in entities
        assert "Company" in entities

    def test_entity_attributes_inferred(self, tmp_path):
        s = _populated(tmp_path)
        entities = s.fetch_database_collection_entities(DB, DB)
        attrs = entities["Person"]["contents"]["attributes"]
        assert "name" in attrs
        assert "age" in attrs

    def test_relations_returned(self, tmp_path):
        s = _populated(tmp_path)
        relations = s.fetch_database_collection_relations(DB, DB)
        assert "WORKS_AT" in relations

    def test_cross_instance_entities(self, tmp_path):
        _populated(tmp_path)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        entities = fresh.fetch_database_collection_entities(DB, DB)
        assert "Person" in entities


# ===========================================================================
# fetch_entity_stats / fetch_property_stats
# ===========================================================================

class TestEntityStats:
    def test_entity_stats_row_count(self, tmp_path):
        s = _populated(tmp_path)
        stats = s.fetch_entity_stats(DB, DB, "Person")
        assert stats["row_count"] == 1

    def test_entity_stats_cross_instance(self, tmp_path):
        _populated(tmp_path)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        stats = fresh.fetch_entity_stats(DB, DB, "Company")
        assert stats["row_count"] == 1

    def test_property_stats_count(self, tmp_path):
        s = _populated(tmp_path)
        s.add_node(DB, "Person", {"name": "Bob", "age": 25})
        stats = s.fetch_property_stats(DB, DB, "Person", "age")
        assert stats["count"] == 2

    def test_property_stats_unique_count(self, tmp_path):
        s = _populated(tmp_path)
        s.add_node(DB, "Person", {"name": "Alice", "age": 30})
        stats = s.fetch_property_stats(DB, DB, "Person", "age")
        assert stats["unique_count"] == 1  # both are 30


# ===========================================================================
# fetch_collection_stats
# ===========================================================================

class TestCollectionStats:
    def test_collection_stats_node_edge_count(self, tmp_path):
        s = _populated(tmp_path)
        stats = s.fetch_collection_stats(DB, DB)
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1

    def test_collection_stats_cross_instance(self, tmp_path):
        _populated(tmp_path)
        fresh = FileGraphSource(name="fg2", directory=str(tmp_path))
        stats = fresh.fetch_collection_stats(DB, DB)
        assert stats["node_count"] == 2
