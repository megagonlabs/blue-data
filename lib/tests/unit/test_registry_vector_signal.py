"""Server-free regression tests for issue #179.

Two bugs made registry search lose all vector signal on Redis:
  1. the per-record KNN filters by @id:{...}, but neither the stored doc nor the
     Redis index had an `id` field, so every lookup returned no rows; and
  2. once the filter matched, Redis returns the embedding as a JSON string, and
     scoring it raised ValueError.

These tests exercise both without a live Redis: a fake vector source returns the
embedding as a string (as Redis does), and the Redis index-build command is
inspected directly.
"""
import json

import pytest

from blue_data.registry.search.indexing import RecordIndexer
from blue_data.registry.search.vector_search import VectorSearch, _coerce_vector


# ---------- _coerce_vector ----------

def test_coerce_vector_accepts_list_and_json_string():
    assert _coerce_vector([1, 2, 3]) == [1.0, 2.0, 3.0]
    assert _coerce_vector("[0.5, 0.25]") == [0.5, 0.25]


def test_coerce_vector_rejects_garbage_without_raising():
    assert _coerce_vector(None) is None
    assert _coerce_vector("not json") is None
    assert _coerce_vector(123) is None


# ---------- score_record with a Redis-like string embedding ----------

class _StringEmbeddingVS:
    """Mimics RedisVectorSource: a matching @id KNN returns the vector as a JSON string."""

    def __init__(self, embedding):
        self._embedding = embedding

    def execute_query(self, query):
        if query.get("op") == "VECTOR.KNN":
            return [{"embedding": json.dumps(self._embedding)}]
        return []


def test_score_record_parses_string_embedding():
    emb = [1.0, 0.0, 0.0, 0.0]
    searcher = VectorSearch(vector_source=_StringEmbeddingVS(emb), index_name="idx", vector_dim=4)
    rec = {"name": "orders", "type": "entity", "scope": "/source/s/database/db/collection/public"}
    score = searcher.score_record(rec, emb, {})
    assert score is not None
    assert score == pytest.approx(1.0, abs=0.05)


def test_score_record_unparseable_embedding_returns_none():
    class _BadVS:
        def execute_query(self, query):
            return [{"embedding": "not-a-vector"}]

    searcher = VectorSearch(vector_source=_BadVS(), index_name="idx", vector_dim=4)
    rec = {"name": "x", "type": "entity", "scope": "/"}
    assert searcher.score_record(rec, [1.0, 0.0, 0.0, 0.0], {}) is None


# ---------- the stored doc carries an `id` the filter can match ----------

def test_indexer_stores_id_field_matching_doc_id():
    captured = {}

    class _CaptureVS:
        def execute_query(self, query):
            if query.get("op") == "VECTOR.UPSERT":
                captured["id"] = query["id"]
                captured["doc"] = query["doc"]
            return "OK"

    indexer = RecordIndexer(
        vector_source=_CaptureVS(), embedding_fn=lambda t: [1.0, 0.0], vector_dim=2
    )
    scope = "/source/s/database/db/collection/public"
    indexer.set_record({"name": "orders", "type": "entity", "scope": scope, "description": "o"})

    assert captured["doc"]["id"] == captured["id"]
    assert captured["doc"]["id"] == f"{scope}/entity/orders"


# ---------- the Redis index declares the `id` TAG ----------

def test_redis_create_index_declares_id_tag():
    pytest.importorskip("redis")
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    rv = RedisVectorSource(
        name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "rv:"}}
    )
    cmd = [str(c) for c in rv._build_create_index_command(
        {"index": "idx", "collection": "coll", "dim": 8}
    )]
    i = cmd.index("id")
    assert cmd[i - 2] == "$.id" and cmd[i - 1] == "AS" and cmd[i + 1] == "TAG"
