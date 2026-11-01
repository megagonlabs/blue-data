"""Regression tests for issue #213.

With an embedding provider configured, build_vector_source defaulted to
MemoryVectorSource regardless of the registry store, and the CLI builds its registry
with rebuild=True. So a single-shot `source sync` embedded every record (billed API
calls) into an in-memory store discarded at process exit, and the next `search` found
no vectors — hybrid search silently degraded to BM25-only.

The vector store now defaults to match the registry store's durability (file->file,
redis->redis, memory->memory), and embedding into a memory store under a durable
registry warns. These tests need no network or Redis: the embedding function is a stub.
"""
import logging

from blue_data.config import build_vector_source
from blue_data.registry.search.indexing import RecordIndexer
from blue_data.source.vector.file_vector_source import FileVectorSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource


def _emb(text):
    return [1.0, 0.0] if ("freight" in text.lower() or "transport" in text.lower()) else [0.0, 1.0]


# ---------- build_vector_source: default follows the registry store ----------

def test_file_store_defaults_to_file_vectors_beside_registry(monkeypatch, tmp_path):
    reg_file = tmp_path / "registry.json"
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_FILE", str(reg_file))
    monkeypatch.delenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", raising=False)
    monkeypatch.delenv("BLUE_DATA_REGISTRY_VECTOR_DIR", raising=False)

    vs = build_vector_source(_emb)
    assert isinstance(vs, FileVectorSource)
    assert vs._directory == str(tmp_path / "vectors")


def test_file_vector_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_DIR", str(tmp_path / "custom"))
    monkeypatch.delenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", raising=False)

    vs = build_vector_source(_emb)
    assert isinstance(vs, FileVectorSource)
    assert vs._directory == str(tmp_path / "custom")


def test_memory_store_defaults_to_memory_vectors_without_warning(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "memory")
    monkeypatch.delenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", raising=False)

    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        vs = build_vector_source(_emb)

    assert isinstance(vs, MemoryVectorSource)
    assert caplog.text == ""  # memory registry + memory vectors is internally consistent


def test_explicit_memory_under_file_store_warns(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "memory")

    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        vs = build_vector_source(_emb)

    assert isinstance(vs, MemoryVectorSource)
    assert "discarded when the process exits" in caplog.text
    assert "file" in caplog.text


def test_explicit_vector_source_overrides_store_default(monkeypatch, tmp_path):
    # A memory registry but an explicit file vector store: honour the override.
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "memory")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_DIR", str(tmp_path / "v"))

    assert isinstance(build_vector_source(_emb), FileVectorSource)


# ---------- the actual bug: embeddings must outlive the command ----------

def test_file_vectors_survive_a_new_process(tmp_path):
    """Index a record through one FileVectorSource, then query through a *fresh* one
    over the same directory (a new CLI process). The paid-for embedding is still there."""
    vdir = str(tmp_path / "vectors")

    writer = RecordIndexer(
        vector_source=FileVectorSource("v", directory=vdir),
        embedding_fn=_emb,
        vector_dim=2,
    )
    writer.set_record({
        "name": "freight",
        "type": "attribute",
        "scope": "/source/shop/database/public/collection/orders",
        "description": "shipping cost",
    })

    # New process: a fresh vector source over the same directory, no re-indexing.
    reader = FileVectorSource("v", directory=vdir)
    results = reader.execute_query({
        "op": "VECTOR.KNN",
        "index": "registry_index",
        "vector": _emb("transport fee"),
        "k": 5,
    })
    assert any(r.get("name") == "freight" for r in results)


def test_memory_vectors_do_not_survive_a_new_process():
    """Contrast: a MemoryVectorSource built fresh (a new process) starts empty — this is
    exactly the lost-embeddings failure #213 fixes by not defaulting to it under a
    durable store."""
    writer = RecordIndexer(
        vector_source=MemoryVectorSource("v"),
        embedding_fn=_emb,
        vector_dim=2,
    )
    writer.set_record({
        "name": "freight",
        "type": "attribute",
        "scope": "/source/shop/database/public/collection/orders",
        "description": "shipping cost",
    })

    reader = MemoryVectorSource("v")  # new process == empty store
    results = reader.execute_query({
        "op": "VECTOR.KNN",
        "index": "registry_index",
        "vector": _emb("transport fee"),
        "k": 5,
    })
    assert results == []
