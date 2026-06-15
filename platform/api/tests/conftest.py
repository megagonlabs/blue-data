import numpy as np
import pytest
from fastapi.testclient import TestClient

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

from registry_api.main import app
from registry_api.deps import get_registry


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
    for i, (cid, total, status) in enumerate(
        [(1, 99.99, "completed"), (2, 49.50, "pending"), (1, 149.0, "completed")], 1
    ):
        reg.execute_query(
            "sales",
            f"INSERT INTO orders VALUES ({i}, {cid}, {total}, '{status}');",
            database="prod",
            optional_properties={"commit": True},
        )
    for i, email in enumerate(["alice@example.com", "bob@example.com"], 1):
        reg.execute_query(
            "sales",
            f"INSERT INTO customers VALUES ({i}, '{email}');",
            database="prod",
            optional_properties={"commit": True},
        )

    reg.set_source_database_collection_entity_description(
        "sales", "prod", "public", "orders", "Customer purchase orders"
    )
    reg.sync_all(recursive=True)
    reg.collect_source_stats("sales", recursive=True)
    return reg


@pytest.fixture
def client(registry):
    app.dependency_overrides[get_registry] = lambda: registry
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
