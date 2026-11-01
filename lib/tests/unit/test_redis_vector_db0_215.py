"""Regression tests for issue #215.

On a Redis db other than 0, RediSearch refuses FT.CREATE ("Cannot create index on
db != 0"). RecordIndexer.ensure_index swallowed that error, every later KNN failed with
"No such index", and registry search silently fell back to BM25. Now:

  * ensure_index lets index-creation failures propagate (no silent swallow);
  * RedisVectorSource rejects db != 0 at construction with a clear error; and
  * build_vector_source disables the Redis vector store (loud WARNING, returns None)
    when the URL selects a db != 0, instead of degrading silently.

The indexer test needs no Redis (a fake vector source raises); the Redis tests skip
when the redis package is absent (clients build lazily, so no live server is needed).
"""
import logging

import pytest

from blue_data.registry.search.indexing import RecordIndexer


# ---------- ensure_index must not swallow create failures ----------

class _RaisingVS:
    def execute_query(self, query):
        if query.get("op") == "VECTOR.CREATE_INDEX":
            raise Exception("Cannot create index on db != 0")
        return []


class _OkVS:
    def __init__(self):
        self.calls = []

    def execute_query(self, query):
        self.calls.append(query.get("op"))
        return "OK"


def test_ensure_index_propagates_create_failure():
    idx = RecordIndexer(vector_source=_RaisingVS(), embedding_fn=lambda t: [0.1], vector_dim=1)
    with pytest.raises(Exception, match="Cannot create index on db != 0"):
        idx.ensure_index()
    # A failed create must not latch _index_ensured (so it isn't treated as done).
    assert idx._index_ensured is False


def test_ensure_index_succeeds_and_latches():
    vs = _OkVS()
    idx = RecordIndexer(vector_source=vs, embedding_fn=lambda t: [0.1], vector_dim=1)
    idx.ensure_index()
    assert idx._index_ensured is True
    assert vs.calls == ["VECTOR.CREATE_INDEX"]


def test_set_record_surfaces_create_failure_rather_than_bm25_only():
    # The crux of #215: indexing a record when the index cannot be created now raises
    # instead of leaving search silently keyword-only.
    idx = RecordIndexer(vector_source=_RaisingVS(), embedding_fn=lambda t: [0.1], vector_dim=1)
    with pytest.raises(Exception, match="Cannot create index on db != 0"):
        idx.set_record({"name": "orders", "type": "entity", "scope": "/source/shop"})


# ---------- RedisVectorSource rejects db != 0 ----------

def test_redis_vector_source_rejects_nonzero_db():
    pytest.importorskip("redis")
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    with pytest.raises(ValueError, match="db 0"):
        RedisVectorSource("v", properties={"connection": {
            "host": "h", "port": 6379, "db": 3, "scan_prefix": "t215:",
        }})


def test_redis_vector_source_accepts_db_0():
    pytest.importorskip("redis")
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    # Default db (0) and explicit 0 both construct (client is lazy — no live server).
    RedisVectorSource("v", properties={"connection": {"host": "h", "port": 6379, "scan_prefix": "t215:"}})
    RedisVectorSource("v", properties={"connection": {"host": "h", "port": 6379, "db": 0, "scan_prefix": "t215:"}})


# ---------- build_vector_source: db != 0 is loud, not silent ----------

def test_build_vector_source_redis_db_nonzero_warns_and_disables(monkeypatch, caplog):
    pytest.importorskip("redis")
    from blue_data.config import build_vector_source

    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_REDIS_URL", "redis://127.0.0.1:6379/3")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "redis")

    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        vs = build_vector_source(embedding_fn=lambda t: [0.0] * 4)

    assert vs is None
    assert "db 0" in caplog.text
    assert "keyword-only" in caplog.text


def test_build_vector_source_redis_db_0_builds(monkeypatch):
    pytest.importorskip("redis")
    from blue_data.config import build_vector_source
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "redis")

    vs = build_vector_source(embedding_fn=lambda t: [0.0] * 4)
    assert isinstance(vs, RedisVectorSource)
