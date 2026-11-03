"""Tests for MemoryVectorSource and FileVectorSource.

Both backends share the same four-op execute_query interface:
    VECTOR.CREATE_INDEX  — create an index pointing at a collection
    VECTOR.UPSERT        — insert/overwrite a doc with an embedding
    VECTOR.DELETE        — remove a doc
    VECTOR.KNN           — nearest-neighbour search
"""
import re

import pytest
import numpy as np

from blue_data.source.vector.memory_vector_source import MemoryVectorSource
from blue_data.source.vector.file_vector_source import FileVectorSource


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DIM = 4

def _vec(*values):
    return list(map(float, values))

def _unit(i, dim=DIM):
    """Unit vector with 1.0 at position i."""
    v = [0.0] * dim
    v[i] = 1.0
    return v

def _doc(doc_id: str, vec, **extra):
    return {"id": doc_id, "embedding": vec, **extra}

def _create(src, index="idx", collection="docs"):
    src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": index,
                       "collection": collection, "dim": DIM})

def _upsert(src, doc_id, vec, collection="docs", **extra):
    return src.execute_query({"op": "VECTOR.UPSERT", "collection": collection,
                               "id": doc_id, "doc": {"embedding": vec, **extra}})

def _delete(src, doc_id, collection="docs"):
    return src.execute_query({"op": "VECTOR.DELETE", "collection": collection, "id": doc_id})

def _knn(src, vec, k=5, index="idx", **kwargs):
    return src.execute_query({"op": "VECTOR.KNN", "index": index,
                               "vector": vec, "k": k, **kwargs})


# ---------------------------------------------------------------------------
# Parametrised fixture — run every test against both backends
# ---------------------------------------------------------------------------

@pytest.fixture(params=["memory", "file"])
def src(request, tmp_path):
    if request.param == "memory":
        return MemoryVectorSource()
    return FileVectorSource(name="fvs", directory=str(tmp_path))


# ===========================================================================
# VECTOR.CREATE_INDEX
# ===========================================================================

def test_create_index_returns_ok(src):
    result = src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "i",
                                 "collection": "c", "dim": DIM})
    assert result == "OK"


def test_create_index_missing_fields_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "i"})


# ===========================================================================
# VECTOR.UPSERT
# ===========================================================================

def test_upsert_returns_ok(src):
    _create(src)
    assert _upsert(src, "d1", _unit(0)) == "OK"


def test_upsert_missing_collection_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.UPSERT", "id": "d1",
                            "doc": {"embedding": _unit(0)}})


def test_upsert_missing_embedding_raises(src):
    _create(src)
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.UPSERT", "collection": "docs",
                            "id": "d1", "doc": {"text": "hello"}})


def test_upsert_overwrites_existing_doc(src):
    _create(src)
    _upsert(src, "d1", _unit(0), label="first")
    _upsert(src, "d1", _unit(1), label="second")
    results = _knn(src, _unit(1), k=1, return_fields=["label"])
    assert results[0]["label"] == "second"


# ===========================================================================
# VECTOR.DELETE
# ===========================================================================

def test_delete_existing_doc(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    assert _delete(src, "d1") == 1  # reports the one document removed
    results = _knn(src, _unit(0), k=10)
    assert all(r["id"] != "d1" for r in results)


def test_delete_missing_doc_returns_zero(src):
    # delete() returns the count actually removed, so a doc that was never stored
    # reports 0 — not 1 (which made callers over-report deletions).
    _create(src)
    assert _delete(src, "ghost") == 0


def test_delete_missing_collection_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.DELETE", "id": "d1"})


# ===========================================================================
# VECTOR.KNN
# ===========================================================================

def test_knn_returns_nearest(src):
    _create(src)
    _upsert(src, "a", _unit(0))
    _upsert(src, "b", _unit(1))
    _upsert(src, "c", _unit(2))
    results = _knn(src, _unit(0), k=1)
    assert results[0]["id"] == "a"


def test_knn_respects_k(src):
    _create(src)
    for i in range(5):
        _upsert(src, f"d{i}", _unit(i % DIM))
    results = _knn(src, _unit(0), k=2)
    assert len(results) <= 2


def test_knn_sorted_by_distance(src):
    _create(src)
    _upsert(src, "close", [1.0, 0.0, 0.0, 0.0])
    _upsert(src, "far",   [0.0, 1.0, 0.0, 0.0])
    results = _knn(src, [1.0, 0.0, 0.0, 0.0], k=2)
    assert results[0]["id"] == "close"
    assert results[1]["id"] == "far"


def test_knn_includes_score(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    results = _knn(src, _unit(0), k=1)
    assert "score" in results[0]
    assert results[0]["score"] == pytest.approx(0.0, abs=1e-5)


def test_knn_custom_score_alias(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    results = _knn(src, _unit(0), k=1, score_alias="dist")
    assert "dist" in results[0]


def test_knn_return_fields_subset(src):
    _create(src)
    _upsert(src, "d1", _unit(0), name="orders", type="entity")
    results = _knn(src, _unit(0), k=1, return_fields=["name"])
    row = results[0]
    assert "name" in row
    assert "type" not in row


def test_knn_empty_index_returns_empty(src):
    _create(src)
    assert _knn(src, _unit(0), k=5) == []


def test_knn_unknown_index_returns_empty(src):
    assert _knn(src, _unit(0), index="no_such_index") == []


def test_knn_missing_index_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.KNN", "vector": _unit(0)})


def test_knn_missing_vector_raises(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.KNN", "index": "idx", "k": 1})


def test_knn_zero_vector_handled(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    # zero query vector → cosine distance = 1.0 (no match by similarity)
    results = _knn(src, [0.0, 0.0, 0.0, 0.0], k=1)
    assert len(results) == 1
    assert results[0]["score"] == pytest.approx(1.0, abs=1e-5)


# ===========================================================================
# Unsupported op
# ===========================================================================

def test_unsupported_op_raises(src):
    with pytest.raises(Exception, match="Unsupported"):
        src.execute_query({"op": "VECTOR.FROBNICATE"})


# ===========================================================================
# MemoryVectorSource — DataSource interface
# ===========================================================================

def test_memory_fetch_source_stats():
    src = MemoryVectorSource()
    _create(src)
    _upsert(src, "d1", _unit(0))
    _upsert(src, "d2", _unit(1))
    stats = src.fetch_source_stats()
    assert stats["total_docs"] == 2


def test_memory_fetch_databases():
    src = MemoryVectorSource()
    _create(src, collection="col_a")
    assert "col_a" in src.fetch_databases()


# ===========================================================================
# FileVectorSource — persistence
# ===========================================================================

def test_file_persists_after_reload(tmp_path):
    src1 = FileVectorSource(name="fvs", directory=str(tmp_path))
    _create(src1)
    _upsert(src1, "d1", _unit(0), name="hello")

    # new instance pointing at same dir
    src2 = FileVectorSource(name="fvs", directory=str(tmp_path))
    results = _knn(src2, _unit(0), k=1)
    assert results[0]["id"] == "d1"


def test_file_index_persists(tmp_path):
    src1 = FileVectorSource(name="fvs", directory=str(tmp_path))
    src1.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "saved_idx",
                         "collection": "docs", "dim": DIM})
    src2 = FileVectorSource(name="fvs", directory=str(tmp_path))
    assert "saved_idx" in src2._indices


def test_file_vector_requires_directory(monkeypatch, tmp_path):
    # #227: must not silently default to the cwd. Refuse construction with no directory
    # and write nothing into the working directory.
    import os
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="directory"):
        FileVectorSource("v")
    assert os.listdir(tmp_path) == []  # nothing scattered into the cwd


def test_file_vector_directory_via_properties(tmp_path):
    src = FileVectorSource("v", properties={"connection": {"directory": str(tmp_path)}})
    assert src._directory == str(tmp_path)


@pytest.mark.parametrize("name", [
    "plain-name.txt", "report (1).txt", "x?y.txt", "a\\b.txt", "brace}x.txt",
])
def test_memory_tag_filter_matches_escaped_special_chars(name):
    # A TAG value with special chars — escaped by the caller as RediSearch TAG
    # syntax — must still match the stored value exactly, including one that
    # contains a closing brace (#149). _unescape_tag restores it before comparing.
    # (MemoryVectorSource only; FileVectorSource does not implement TAG filters.)
    src = MemoryVectorSource()
    src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx",
                       "collection": "docs", "dim": DIM})
    _upsert(src, "d1", _unit(0), file_name=name)
    _upsert(src, "d2", _unit(1), file_name="other.txt")

    escaped = re.sub(r"(\W)", r"\\\1", name)  # what the doc-source layer sends
    results = _knn(src, _unit(0), k=5, return_fields=["file_name"],
                   filter=f"@file_name:{{{escaped}}}")
    assert [r["file_name"] for r in results] == [name]
