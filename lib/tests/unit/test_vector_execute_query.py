"""Unit tests for VectorSource.execute_query on MemoryVectorSource and FileVectorSource."""
import pytest

from blue_data.source.vector.memory_vector_source import MemoryVectorSource
from blue_data.source.vector.file_vector_source import FileVectorSource


def _sources(tmp_path):
    return [
        MemoryVectorSource("mem"),
        FileVectorSource("file", directory=str(tmp_path)),
    ]


def _vec(seed: float, dim: int = 4) -> list[float]:
    """Return a simple unit vector seeded by a scalar."""
    import math
    base = [seed * (i + 1) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in base))
    return [x / norm for x in base]


class TestCreateIndex:
    def test_create_index_returns_ok(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query(
                {"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4}
            )
            assert result == "OK"

    def test_create_index_custom_metric(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query(
                {"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4, "distance_metric": "L2"}
            )
            assert result == "OK"


class TestUpsert:
    def test_upsert_returns_ok(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            result = src.execute_query(
                {"op": "VECTOR.UPSERT", "collection": "docs", "id": "doc-1", "doc": {"embedding": _vec(1.0), "text": "hello"}}
            )
            assert result == "OK"

    def test_upsert_missing_embedding_raises(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            with pytest.raises(Exception, match="embedding"):
                src.execute_query(
                    {"op": "VECTOR.UPSERT", "collection": "docs", "id": "doc-1", "doc": {"text": "no embedding"}}
                )


class TestDelete:
    def test_delete_returns_count(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            src.execute_query(
                {"op": "VECTOR.UPSERT", "collection": "docs", "id": "doc-1", "doc": {"embedding": _vec(1.0)}}
            )
            result = src.execute_query({"op": "VECTOR.DELETE", "collection": "docs", "id": "doc-1"})
            assert result == 1

    def test_delete_nonexistent_does_not_raise(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            src.execute_query({"op": "VECTOR.DELETE", "collection": "docs", "id": "ghost"})


class TestKNN:
    def test_knn_returns_nearest(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            for i in range(1, 4):
                src.execute_query({
                    "op": "VECTOR.UPSERT",
                    "collection": "docs",
                    "id": f"doc-{i}",
                    "doc": {"embedding": _vec(float(i)), "label": f"item-{i}"},
                })
            results = src.execute_query(
                {"op": "VECTOR.KNN", "index": "idx", "vector": _vec(1.0), "k": 1}
            )
            assert len(results) == 1
            assert results[0]["id"] == "doc-1"

    def test_knn_respects_k(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            for i in range(1, 6):
                src.execute_query({
                    "op": "VECTOR.UPSERT",
                    "collection": "docs",
                    "id": f"doc-{i}",
                    "doc": {"embedding": _vec(float(i))},
                })
            results = src.execute_query(
                {"op": "VECTOR.KNN", "index": "idx", "vector": _vec(1.0), "k": 3}
            )
            assert len(results) == 3

    def test_knn_unknown_index_returns_empty(self, tmp_path):
        for src in _sources(tmp_path):
            results = src.execute_query(
                {"op": "VECTOR.KNN", "index": "no-such-index", "vector": _vec(1.0)}
            )
            assert results == []

    def test_knn_missing_vector_raises(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            with pytest.raises(ValueError, match="query vector"):
                src.execute_query({"op": "VECTOR.KNN", "index": "idx", "k": 3})

    def test_knn_score_alias(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx", "collection": "docs", "dim": 4})
            src.execute_query({
                "op": "VECTOR.UPSERT", "collection": "docs", "id": "d1",
                "doc": {"embedding": _vec(1.0)},
            })
            results = src.execute_query(
                {"op": "VECTOR.KNN", "index": "idx", "vector": _vec(1.0), "score_alias": "dist"}
            )
            assert "dist" in results[0]


class TestErrors:
    def test_non_dict_query_raises(self, tmp_path):
        src = MemoryVectorSource("mem")
        with pytest.raises(ValueError, match="expects query as a dict"):
            src.execute_query("VECTOR.KNN idx vec")

    def test_unknown_op_raises(self, tmp_path):
        src = MemoryVectorSource("mem")
        with pytest.raises(ValueError, match="Unsupported"):
            src.execute_query({"op": "VECTOR.SEARCH", "index": "idx"})


# ---------------------------------------------------------------------------
# execute_query_nl
# ---------------------------------------------------------------------------

def _embed(text: str, dim: int = 4) -> list[float]:
    """Deterministic embedding: hash the text into a unit vector."""
    import math
    seed = abs(hash(text)) % 1000 + 1
    base = [seed * (i + 1) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in base))
    return [x / norm for x in base]


def _populated_src(embedding_fn=None) -> MemoryVectorSource:
    """MemoryVectorSource pre-loaded with two docs."""
    src = MemoryVectorSource("mem", embedding_fn=embedding_fn)
    src.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "docs", "collection": "docs", "dim": 4})
    for label in ("apple", "banana"):
        src.execute_query({
            "op": "VECTOR.UPSERT",
            "collection": "docs",
            "id": label,
            "doc": {"text": label, "embedding": _embed(label)},
        })
    return src


class TestExecuteQueryNL:
    def test_returns_empty_without_embedding_fn(self):
        src = _populated_src(embedding_fn=None)
        result = src.execute_query_nl("apple", collection="docs")
        assert result == []

    def test_returns_empty_without_collection_or_index(self):
        src = _populated_src(embedding_fn=_embed)
        result = src.execute_query_nl("apple")
        assert result == []

    def test_embedding_fn_from_constructor(self):
        src = _populated_src(embedding_fn=_embed)
        results = src.execute_query_nl("apple", collection="docs")
        assert len(results) > 0
        ids = [r["id"] for r in results]
        assert "apple" in ids

    def test_embedding_fn_from_optional_properties(self):
        src = _populated_src(embedding_fn=None)
        results = src.execute_query_nl(
            "apple",
            collection="docs",
            optional_properties={"embedding_fn": _embed},
        )
        assert len(results) > 0

    def test_optional_properties_embedding_fn_takes_precedence(self):
        wrong_embed = lambda text: [0.0, 0.0, 0.0, 1.0]
        src = _populated_src(embedding_fn=wrong_embed)
        results = src.execute_query_nl(
            "apple",
            collection="docs",
            optional_properties={"embedding_fn": _embed},
        )
        ids = [r["id"] for r in results]
        assert "apple" in ids

    def test_index_from_optional_properties_overrides_collection(self):
        src = _populated_src(embedding_fn=_embed)
        results = src.execute_query_nl(
            "apple",
            collection="wrong_collection",
            optional_properties={"index": "docs"},
        )
        assert len(results) > 0

    def test_k_limits_results(self):
        src = _populated_src(embedding_fn=_embed)
        results = src.execute_query_nl(
            "apple", collection="docs", optional_properties={"k": 1}
        )
        assert len(results) == 1

    def test_nearest_neighbour_is_self(self):
        src = _populated_src(embedding_fn=_embed)
        results = src.execute_query_nl("apple", collection="docs", optional_properties={"k": 1})
        assert results[0]["id"] == "apple"
