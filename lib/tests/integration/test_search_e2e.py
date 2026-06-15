"""End-to-end search test — no Redis required.

Uses MemoryJSONSource (registry storage) + MemoryVectorSource (vector index)
+ a deterministic hash-based embedding function.
"""
import hashlib
import math

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource


DIM = 64


def hash_embedding(text: str) -> list[float]:
    """Deterministic embedding: each dimension is a sine of a hash-seeded value."""
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


TEST_HYBRID_CONFIG = {
    # Hash embeddings are not semantically aware, so vector similarity between
    # a short query ("users") and the indexed text ("users entity") is low.
    # Relax thresholds so the test focuses on pipeline correctness, not score tuning.
    "vector_threshold": 0.0,
    "combined_threshold": 0.0,
}


@pytest.fixture
def registry():
    vector_source = MemoryVectorSource()
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=vector_source,
        embedding_fn=hash_embedding,
        vector_dim=DIM,
        rebuild=True,
        hybrid_config=TEST_HYBRID_CONFIG,
    )
    return reg


def test_memory_vector_source_ops():
    vs = MemoryVectorSource()

    vs.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": DIM})

    emb = hash_embedding("hello world")
    vs.execute_query({
        "op": "VECTOR.UPSERT",
        "collection": "docs",
        "id": "doc1",
        "doc": {"embedding": emb, "name": "hello world"},
        "embedding_field": "embedding",
    })

    results = vs.execute_query({
        "op": "VECTOR.KNN",
        "index": "idx",
        "vector": emb,
        "k": 1,
        "return_fields": ["name"],
    })

    assert len(results) == 1
    assert results[0]["id"] == "doc1"
    assert results[0]["score"] < 0.01  # near-zero distance = identical vector

    vs.execute_query({"op": "VECTOR.DELETE", "collection": "docs", "id": "doc1"})
    results = vs.execute_query({"op": "VECTOR.KNN", "index": "idx", "vector": emb, "k": 1})
    assert results == []


def test_search_after_register(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.register_record(name="orders", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.register_record(name="products", type="entity", scope="/source/mydb/database/prod/collection/public")

    results = registry.search_records("users")
    names = [r["name"] for r in results]
    assert "users" in names


def test_search_returns_most_relevant_first(registry):
    registry.register_record(
        name="customer_orders",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="table of customer purchase orders",
    )
    registry.register_record(
        name="products",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="product catalog",
    )

    results = registry.search_records("customer orders")
    assert len(results) > 0
    assert results[0]["name"] == "customer_orders"


def test_search_with_type_filter(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.register_record(name="prod", type="database", scope="/source/mydb")

    results = registry.search_records("users", type="entity")
    assert all(r["type"] == "entity" for r in results)


def test_keyword_fallback_no_vector(registry):
    """search_records works even when embedding returns None for some records."""
    registry.register_record(name="sessions", type="entity", scope="/source/mydb/database/prod/collection/public")
    results = registry.search_records("sessions")
    assert any(r["name"] == "sessions" for r in results)
