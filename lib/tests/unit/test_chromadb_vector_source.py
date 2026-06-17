"""Unit tests for ChromaDBVectorSource.

Uses chromadb.EphemeralClient — fully in-memory, no server required.
Skipped automatically when the chromadb package is not installed.
"""
import pytest

chromadb = pytest.importorskip("chromadb", reason="chromadb not installed")
from blue_data.source.vector.chromadb.chromadb_vector_source import ChromaDBVectorSource

DIM = 4


def _unit(i, dim=DIM):
    v = [0.0] * dim
    v[i % dim] = 1.0
    return v


@pytest.fixture
def src():
    source = ChromaDBVectorSource(name="test_chroma")
    yield source
    source._client.reset()


def _create(src, index="idx", collection="docs"):
    return src.execute_query({
        "op": "VECTOR.CREATE_INDEX",
        "index": index,
        "collection": collection,
        "dim": DIM,
    })


def _upsert(src, doc_id, vec, collection="docs", **extra):
    return src.execute_query({
        "op": "VECTOR.UPSERT",
        "collection": collection,
        "id": doc_id,
        "doc": {"embedding": vec, **extra},
    })


def _delete(src, doc_id, collection="docs"):
    return src.execute_query({
        "op": "VECTOR.DELETE",
        "collection": collection,
        "id": doc_id,
    })


def _knn(src, vec, k=5, index="idx", **kwargs):
    return src.execute_query({
        "op": "VECTOR.KNN",
        "index": index,
        "vector": vec,
        "k": k,
        **kwargs,
    })


# ===========================================================================
# VECTOR.CREATE_INDEX
# ===========================================================================

def test_create_index_returns_ok(src):
    assert _create(src) == "OK"


def test_create_index_missing_index_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.CREATE_INDEX", "collection": "c"})


def test_create_index_missing_collection_raises(src):
    with pytest.raises(Exception):
        src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "i"})


def test_create_index_registers_in_indices(src):
    _create(src, index="myidx", collection="mycol")
    assert "myidx" in src._indices
    assert src._indices["myidx"]["collection"] == "mycol"


def test_create_index_custom_distance_metric(src):
    result = src.execute_query({
        "op": "VECTOR.CREATE_INDEX",
        "index": "l2_idx",
        "collection": "l2_col",
        "dim": DIM,
        "distance_metric": "L2",
    })
    assert result == "OK"


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
                            "id": "d1", "doc": {"text": "no embedding"}})


def test_upsert_overwrites_existing(src):
    _create(src)
    _upsert(src, "d1", _unit(0), label="first")
    _upsert(src, "d1", _unit(1), label="second")
    results = _knn(src, _unit(1), k=1, return_fields=["label"])
    assert results[0]["label"] == "second"


def test_upsert_ignores_non_scalar_metadata(src):
    _create(src)
    # list values are not valid ChromaDB metadata — must not crash
    result = _upsert(src, "d1", _unit(0), tags=["a", "b"], name="ok")
    assert result == "OK"


# ===========================================================================
# VECTOR.DELETE
# ===========================================================================

def test_delete_returns_one(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    assert _delete(src, "d1") == 1


def test_delete_removes_doc_from_results(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    _upsert(src, "d2", _unit(1))
    _delete(src, "d1")
    results = _knn(src, _unit(0), k=10)
    assert all(r["id"] != "d1" for r in results)


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


def test_knn_custom_score_alias(src):
    _create(src)
    _upsert(src, "d1", _unit(0))
    results = _knn(src, _unit(0), k=1, score_alias="dist")
    assert "dist" in results[0]
    assert "score" not in results[0]


def test_knn_return_fields_subset(src):
    _create(src)
    _upsert(src, "d1", _unit(0), name="orders", kind="entity")
    results = _knn(src, _unit(0), k=1, return_fields=["name"])
    assert "name" in results[0]
    assert "kind" not in results[0]


def test_knn_returns_all_metadata_when_no_return_fields(src):
    _create(src)
    _upsert(src, "d1", _unit(0), name="orders", kind="entity")
    results = _knn(src, _unit(0), k=1)
    assert "name" in results[0]
    assert "kind" in results[0]


def test_knn_includes_id(src):
    _create(src)
    _upsert(src, "my-doc", _unit(0))
    results = _knn(src, _unit(0), k=1)
    assert results[0]["id"] == "my-doc"


# ===========================================================================
# Unsupported op
# ===========================================================================

def test_unsupported_op_raises(src):
    with pytest.raises(Exception, match="Unsupported"):
        src.execute_query({"op": "VECTOR.FROBNICATE"})


def test_non_dict_query_raises(src):
    with pytest.raises(Exception):
        src.execute_query("SELECT 1")
