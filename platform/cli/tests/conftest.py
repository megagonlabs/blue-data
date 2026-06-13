import numpy as np
import pytest
from click.testing import CliRunner

from registry.data_registry import DataRegistry
from registry.enrichment.metadata import MetaData
from source.json.memory_json_source import MemoryJSONSource
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from source.vector.memory_vector_source import MemoryVectorSource

import registry_cli.config as config_module
from registry_cli.main import cli


def _embed(text: str) -> list:
    rng = np.random.RandomState(abs(hash(text)) % (2 ** 31))
    return rng.randn(64).tolist()


@pytest.fixture
def registry(tmp_path):
    source = SQLiteDBSource(
        name="sales",
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
    reg.create_source_database("sales", "prod", overwrite=True)
    reg.create_source_database_collection_entity(
        "sales", "prod", "public", "orders",
        creation_properties={
            "cols_definition": [
                {"name": "id",     "type": "INTEGER"},
                {"name": "total",  "type": "REAL"},
                {"name": "status", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    reg.create_source_database_collection_entity(
        "sales", "prod", "public", "customers",
        creation_properties={
            "cols_definition": [
                {"name": "id",    "type": "INTEGER"},
                {"name": "email", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    for i, (total, status) in enumerate([(99.99, "completed"), (49.50, "pending")], 1):
        reg.execute_query(
            "sales",
            f"INSERT INTO orders VALUES ({i}, {total}, '{status}');",
            database="prod",
            optional_properties={"commit": True},
        )
    reg.sync_all(recursive=True)
    reg.collect_source_stats("sales", recursive=True)
    return reg


@pytest.fixture(autouse=True)
def inject_registry(registry):
    config_module._registry = registry
    yield
    config_module._registry = None


@pytest.fixture
def runner():
    return CliRunner()
