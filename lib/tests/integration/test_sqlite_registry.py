import pytest
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


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


def test_enrich_source_metadata_deterministic(tmp_path):
    """enrich_source_metadata without an LLM runs the deterministic base layer
    (SemanticTypeInferencer) and the deterministic parts of MetaData
    (process semantics, value axis, semantic roles) — nothing should raise."""
    source = SQLiteDBSource(
        name="sqlite",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    enricher = MetaData(llm_fn=None)
    registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)
    registry.register_source(source)

    registry.create_source_database("sqlite", "events", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "events", "public", "purchases",
        creation_properties={
            "cols_definition": [
                {"name": "id", "type": "INTEGER"},
                {"name": "user_id", "type": "INTEGER"},
                {"name": "purchase_date", "type": "TEXT"},
                {"name": "amount", "type": "REAL"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    for i in range(1, 21):
        registry.execute_query(
            source="sqlite",
            database="events",
            query=f"INSERT INTO purchases VALUES ({i}, {i % 5}, '2023-{(i % 12) + 1:02d}-01', {float(i * 9.99)});",
            optional_properties={"commit": True},
        )
    registry.sync_all(recursive=True)
    registry.collect_source_stats("sqlite", recursive=True)

    # must not raise
    registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)

    # base-layer VSI must be written for all attributes
    for attr_name in ("user_id", "purchase_date", "amount"):
        sem = registry.get_source_database_collection_entity_attribute_property(
            "sqlite", "events", "public", "purchases", attr_name, "value_semantics"
        )
        assert sem is not None, f"value_semantics missing for {attr_name}"
        assert "semantic_type" in sem


def test_enrich_source_metadata_with_stub_llm(tmp_path):
    """When an llm_fn is provided, VSI is written via the LLM path and must
    not overwrite existing VSI on a second pass (rebuild=False)."""

    call_log = []

    def stub_llm(prompt: str) -> str:
        call_log.append(prompt)
        # Return minimal valid JSON for every prompt type
        if "value_semantics" in prompt:
            return '{"value_semantics": {"semantic_type": "INTEGER", "primary_type": "INTEGER", "confidence": 0.9, "is_identifier": false, "is_categorical": false, "is_free_text": false, "numeric": {"is_numeric": true, "is_continuous": false, "is_discrete": true, "min": null, "max": null}, "temporal": {"is_date": false, "is_datetime": false, "is_duration": false, "granularity": null}, "normalization": {"can_normalize": false, "normalized_examples": [], "normalization_strategy": null}, "examples_used": [], "notes": []}}'
        if "semantic_type" in prompt and "subcategory" in prompt:
            return '{"semantic_type": "INTEGER", "subcategory": null, "confidence": 0.8, "range": {"min": null, "max": null}, "criteria": null, "rationale": "numeric id", "examples": []}'
        if "table_description" in prompt:
            return '{"table_description": "purchase events", "attributes": {}}'
        return "{}"

    source = SQLiteDBSource(
        name="sqlite",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    enricher = MetaData(llm_fn=stub_llm)
    registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)
    registry.register_source(source)

    registry.create_source_database("sqlite", "sales", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "sales", "public", "orders",
        creation_properties={
            "cols_definition": [
                {"name": "order_id", "type": "INTEGER"},
                {"name": "total", "type": "REAL"},
            ],
            "primary_key": ["order_id"],
        },
        overwrite=True,
    )
    for order_id, total in [(1, 29.99), (2, 49.99)]:
        registry.execute_query(
            source="sqlite",
            database="sales",
            query=f"INSERT INTO orders VALUES ({order_id}, {total});",
            optional_properties={"commit": True},
        )
    registry.sync_all(recursive=True)
    registry.collect_source_stats("sqlite", recursive=True)

    registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)

    first_call_count = len(call_log)
    assert first_call_count > 0, "LLM was never called"

    # second pass with rebuild=False must not re-invoke LLM for existing VSI
    registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
    assert len(call_log) == first_call_count, "LLM was called again despite rebuild=False"
