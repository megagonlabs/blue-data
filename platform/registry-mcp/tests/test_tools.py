"""Tests for registry-mcp tool functions.

Each test injects a pre-built in-memory DataRegistry as the server singleton
so no real data sources or environment variables are needed.
"""
import json
import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

import numpy as np

import registry_mcp.config as config_module
from registry_mcp.server import (
    search_records,
    list_sources,
    list_source_databases,
    list_database_collections,
    list_collection_entities,
    get_entity,
    get_record,
    sync_source,
    collect_source_stats,
    enrich_source,
    enrich_source_metadata,
    execute_query,
    import_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _embed(text: str) -> list:
    """Deterministic embedding for tests — no external deps."""
    rng = np.random.RandomState(abs(hash(text)) % (2 ** 31))
    return rng.randn(64).tolist()


@pytest.fixture
def registry(tmp_path):
    """Pre-populated in-memory registry with a SQLite source."""
    source = SQLiteDBSource(
        name="testdb",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource(),
        embedding_fn=_embed,
        vector_dim=64,
        rebuild=True,
        hybrid_config={"combined_threshold": 0.0, "vector_threshold": 0.0},
        metadata_enricher=MetaData(llm_fn=None),
    )
    reg.register_source(source)

    reg.create_source_database("testdb", "sales", overwrite=True)
    reg.create_source_database_collection_entity(
        "testdb", "sales", "public", "orders",
        creation_properties={
            "cols_definition": [
                {"name": "id",          "type": "INTEGER"},
                {"name": "customer_id", "type": "INTEGER"},
                {"name": "total",       "type": "REAL"},
                {"name": "status",      "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    reg.create_source_database_collection_entity(
        "testdb", "sales", "public", "customers",
        creation_properties={
            "cols_definition": [
                {"name": "id",    "type": "INTEGER"},
                {"name": "email", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )

    for i, (cid, total, status) in enumerate(
        [(1, 99.99, "completed"), (2, 49.50, "pending"), (1, 149.0, "completed")], 1
    ):
        reg.execute_query(
            "testdb",
            f"INSERT INTO orders VALUES ({i}, {cid}, {total}, '{status}');",
            database="sales",
            optional_properties={"commit": True},
        )
    for i, email in enumerate(["alice@example.com", "bob@example.com"], 1):
        reg.execute_query(
            "testdb",
            f"INSERT INTO customers VALUES ({i}, '{email}');",
            database="sales",
            optional_properties={"commit": True},
        )

    reg.set_source_database_collection_entity_description(
        "testdb", "sales", "public", "orders", "Customer purchase orders"
    )

    reg.sync_all(recursive=True)
    reg.collect_source_stats("testdb", recursive=True)
    return reg


@pytest.fixture(autouse=True)
def inject_registry(registry):
    """Wire the test registry as the MCP server singleton."""
    config_module._registry = registry
    yield
    config_module._registry = None


# ---------------------------------------------------------------------------
# Explore tools
# ---------------------------------------------------------------------------

def test_list_sources():
    result = json.loads(list_sources())
    assert "testdb" in result


def test_list_source_databases():
    result = json.loads(list_source_databases("testdb"))
    names = [r["name"] for r in result]
    assert "sales" in names


def test_list_database_collections():
    result = json.loads(list_database_collections("testdb", "sales"))
    names = [r["name"] for r in result]
    assert "public" in names


def test_list_collection_entities():
    result = json.loads(list_collection_entities("testdb", "sales", "public"))
    names = [r["name"] for r in result]
    assert "orders" in names
    assert "customers" in names


def test_search_records_returns_results():
    # keyword-only search (no vector source); use an exact name that is in the registry
    result = json.loads(search_records("orders", record_type="entity"))
    assert len(result) > 0
    names = [r["name"] for r in result]
    assert "orders" in names


def test_search_records_type_filter():
    result = json.loads(search_records("orders", record_type="entity"))
    assert all(r["type"] == "entity" for r in result)


def test_search_records_limit():
    result = json.loads(search_records("orders", limit=1))
    assert len(result) <= 1


def test_search_records_empty_query_returns_no_error():
    result = json.loads(search_records("xyzzy_not_in_registry"))
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Inspect tools
# ---------------------------------------------------------------------------

def test_get_entity_returns_record_with_attributes():
    result = json.loads(get_entity("testdb", "sales", "public", "orders"))
    assert result["name"] == "orders"
    assert "attributes" in result
    attr_names = [a["name"] for a in result["attributes"]]
    assert "id" in attr_names
    assert "total" in attr_names
    assert "status" in attr_names


def test_get_entity_attributes_have_stats():
    result = json.loads(get_entity("testdb", "sales", "public", "orders"))
    attr_by_name = {a["name"]: a for a in result["attributes"]}
    assert "stats" in attr_by_name["total"]
    assert "sample_values" in attr_by_name["total"]["stats"]


def test_get_entity_description_preserved():
    result = json.loads(get_entity("testdb", "sales", "public", "orders"))
    assert result.get("description") == "Customer purchase orders"


def test_get_entity_not_found_returns_error():
    result = json.loads(get_entity("testdb", "sales", "public", "nonexistent"))
    assert "error" in result


def test_get_record_by_identity():
    scope = "/source/testdb/database/sales/collection/public"
    result = json.loads(get_record("orders", "entity", scope))
    assert result["name"] == "orders"
    assert result["type"] == "entity"


def test_get_record_not_found_returns_error():
    result = json.loads(get_record("ghost", "entity", "/source/testdb/database/sales/collection/public"))
    assert "error" in result


# ---------------------------------------------------------------------------
# Manage tools
# ---------------------------------------------------------------------------

def test_sync_source_returns_ok():
    result = json.loads(sync_source("testdb"))
    assert result["status"] == "ok"
    assert result["source"] == "testdb"


def test_sync_source_idempotent(registry):
    before = registry.list_collection_entities("testdb", "sales", "public")
    json.loads(sync_source("testdb"))
    after = registry.list_collection_entities("testdb", "sales", "public")
    assert {e["name"] for e in before} == {e["name"] for e in after}


def test_collect_source_stats_returns_ok():
    result = json.loads(collect_source_stats("testdb"))
    assert result["status"] == "ok"


def test_enrich_source_writes_value_semantics(registry):
    json.loads(enrich_source("testdb"))
    sem = registry.get_source_database_collection_entity_attribute_property(
        "testdb", "sales", "public", "orders", "total", "value_semantics"
    )
    assert sem is not None
    assert sem["semantic_type"] == "FLOAT"


def test_enrich_source_email_detection(registry):
    json.loads(enrich_source("testdb"))
    sem = registry.get_source_database_collection_entity_attribute_property(
        "testdb", "sales", "public", "customers", "email", "value_semantics"
    )
    assert sem is not None
    assert sem["semantic_type"] == "EMAIL"


def test_enrich_source_metadata_deterministic(registry):
    json.loads(enrich_source_metadata("testdb", recursive=True, rebuild=False))
    role = registry.get_source_database_collection_entity_attribute_property(
        "testdb", "sales", "public", "orders", "total", "semantic_role"
    )
    assert role is not None
    assert "primary_role" in role


def test_enrich_source_metadata_idempotent(registry):
    json.loads(enrich_source_metadata("testdb", recursive=True, rebuild=False))
    sem_first = registry.get_source_database_collection_entity_attribute_property(
        "testdb", "sales", "public", "orders", "total", "value_semantics"
    )
    json.loads(enrich_source_metadata("testdb", recursive=True, rebuild=False))
    sem_second = registry.get_source_database_collection_entity_attribute_property(
        "testdb", "sales", "public", "orders", "total", "value_semantics"
    )
    assert sem_first == sem_second


def test_enrich_source_metadata_rebuild_overwrites(registry):
    json.loads(enrich_source_metadata("testdb", recursive=True, rebuild=False))
    result = json.loads(enrich_source_metadata("testdb", recursive=True, rebuild=True))
    assert result["status"] == "ok"
    assert result["rebuild"] is True


def test_manage_tools_unknown_source_return_error():
    # sync and collect_stats raise when the source is not registered
    assert "error" in json.loads(sync_source("no_such_source"))
    assert "error" in json.loads(collect_source_stats("no_such_source"))
    # enrich_source silently no-ops on an unknown source (iterates empty list)
    result = json.loads(enrich_source("no_such_source"))
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Query tools
# ---------------------------------------------------------------------------

def test_execute_query_returns_rows():
    result = json.loads(execute_query("testdb", "SELECT * FROM orders", database="sales"))
    assert isinstance(result, list)
    assert len(result) == 3
    assert "total" in result[0]


def test_execute_query_unknown_source_returns_error():
    result = json.loads(execute_query("no_such_source", "SELECT 1"))
    assert "error" in result


def test_import_data_copies_rows(registry, tmp_path):
    """Import rows from a FileSource CSV into the existing testdb SQLite source."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files"
    d.mkdir()
    pd.DataFrame([
        {"id": 10, "customer_id": 1, "total": 9.99,  "status": "new"},
        {"id": 11, "customer_id": 2, "total": 19.99, "status": "new"},
    ]).to_csv(d / "new_orders.csv", index=False)

    file_src = FileSource("filesrc", directory=str(d))
    registry.register_source(file_src)

    result = json.loads(import_data(
        source="filesrc",
        target="testdb",
        collection="new_orders",
        database="sales",
        entity="orders",
        mode="append",
    ))
    assert result["status"] == "success"
    assert result["rows_imported"] == 2

    rows = json.loads(execute_query("testdb", "SELECT * FROM orders", database="sales"))
    assert len(rows) == 5  # 3 original + 2 imported


def test_import_data_unknown_source_returns_error():
    result = json.loads(import_data(
        source="no_such_source",
        target="testdb",
        collection="orders",
    ))
    assert "error" in result


def test_import_data_unknown_target_returns_error():
    result = json.loads(import_data(
        source="testdb",
        target="no_such_target",
        collection="orders",
    ))
    assert "error" in result


def test_import_data_missing_entity_returns_error(registry, tmp_path):
    """SQL targets require entity; omitting it should return an error."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files2"
    d.mkdir()
    pd.DataFrame([{"id": 1, "val": "x"}]).to_csv(d / "data.csv", index=False)

    file_src = FileSource("filesrc2", directory=str(d))
    registry.register_source(file_src)

    result = json.loads(import_data(
        source="filesrc2",
        target="testdb",
        collection="data",
        database="sales",
        entity=None,
    ))
    assert "error" in result
