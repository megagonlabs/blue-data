import pytest
from registry.data_registry import DataRegistry
from source.json.memory_json_source import MemoryJSONSource
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def registry(tmp_path):
    source = SQLiteDBSource(
        name="sqlite",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(source)
    return reg


def test_register_source(registry):
    assert "sqlite" in registry.list_sources()


def test_create_and_sync_database(registry):
    registry.create_source_database("sqlite", "testdb", overwrite=True)
    dbs = [r["name"] for r in registry.list_source_databases("sqlite")]
    assert "testdb" in dbs


def test_create_entity_and_sync(registry):
    registry.create_source_database("sqlite", "testdb", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "testdb", "public", "users",
        creation_properties={
            "cols_definition": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    entities = registry.list_collection_entities("sqlite", "testdb", "public")
    assert any(e["name"] == "users" for e in entities)


def test_collect_entity_stats(registry):
    registry.create_source_database("sqlite", "testdb", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "testdb", "public", "users",
        creation_properties={
            "cols_definition": [
                {"name": "id", "type": "INTEGER"},
                {"name": "age", "type": "INTEGER"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    registry.execute_query(
        source="sqlite",
        database="testdb",
        query="INSERT INTO users VALUES (1, 25);",
        optional_properties={"commit": True},
    )
    registry.sync_all(recursive=True)
    stats = registry.collect_source_database_collection_entity_stats(
        "sqlite", "testdb", "public", "users"
    )
    assert stats["row_count"] == 1


def test_semantic_enrichment(registry):
    registry.create_source_database("sqlite", "testdb", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "testdb", "public", "users",
        creation_properties={
            "cols_definition": [
                {"name": "id", "type": "INTEGER"},
                {"name": "age", "type": "INTEGER"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    registry.execute_query(
        source="sqlite",
        database="testdb",
        query="INSERT INTO users VALUES (1, 30);",
        optional_properties={"commit": True},
    )
    registry.sync_all(recursive=True)
    registry.collect_source_stats("sqlite", recursive=True)
    registry.enrich_source("sqlite")

    semantics = registry.get_source_database_collection_entity_attribute_property(
        "sqlite", "testdb", "public", "users", "age", "value_semantics"
    )
    assert semantics["semantic_type"] == "INTEGER"
