"""Regression tests for issue #180.

RedisVectorSource returned the KNN score as a string (e.g. '4.99e-05'), while
MemoryVectorSource returns a float. Consumers that sort on the score then got
lexicographic order and ranked the wrong hit first. The Redis reply parsers now
coerce the score field to float. Server-free: the parsers are exercised directly
on synthetic RESP2/RESP3 replies.
"""
import pytest

from blue_data.source.vector.memory_vector_source import MemoryVectorSource

pytest.importorskip("redis")
from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource


def _src():
    return RedisVectorSource(
        name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "x:"}}
    )


def test_resp2_score_coerced_to_float_and_sorts_numerically():
    rows = _src()._parse_search_results([
        2,
        b"climate", [b"score", b"4.99486923218e-05", b"name", b"Climate"],
        b"sports", [b"score", b"0.392030358315", b"name", b"Sports"],
    ])
    assert all(isinstance(r["score"], float) for r in rows)
    rows.sort(key=lambda r: r["score"])  # would raise/misorder on strings
    assert rows[0]["id"] == "climate"


def test_resp3_score_coerced_to_float():
    rows = _src()._parse_search_results({
        "results": [
            {"id": "climate", "extra_attributes": {"score": "4.99e-05", "name": "Climate"}},
            {"id": "sports", "extra_attributes": {"score": "0.392", "name": "Sports"}},
        ]
    })
    assert all(isinstance(r["score"], float) for r in rows)


def test_custom_score_alias_is_coerced():
    rows = _src()._parse_search_results([1, b"a", [b"dist", b"0.5"]], score_field="dist")
    assert rows[0]["dist"] == 0.5 and isinstance(rows[0]["dist"], float)


def test_non_numeric_score_is_left_unchanged():
    rows = _src()._parse_search_results([1, b"a", [b"score", b"n/a"]])
    assert rows[0]["score"] == "n/a"


def test_score_type_matches_memory_backend():
    mem = MemoryVectorSource()
    mem.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "i", "collection": "c", "dim": 2})
    mem.execute_query({
        "op": "VECTOR.UPSERT", "collection": "c", "id": "a",
        "doc": {"embedding": [1.0, 0.0]}, "embedding_field": "embedding",
    })
    mem_rows = mem.execute_query({"op": "VECTOR.KNN", "index": "i", "vector": [1.0, 0.0], "k": 1})
    redis_rows = _src()._parse_search_results([1, b"a", [b"score", b"0.5"]])
    assert type(redis_rows[0]["score"]) is type(mem_rows[0]["score"]) is float
