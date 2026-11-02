"""Regression tests for issue #139.

The VectorSource ABC had no way to enumerate or bulk-delete doc ids, and delete()
returned 1 unconditionally on several backends — so cleaning a re-ingested page's stale
chunks needed an external freshness store (the prior chunk_count). This adds
list_ids(collection, prefix=None) and delete_by_prefix(collection, prefix) to the ABC and
all four backends, and makes delete() honor its "count deleted" contract everywhere.

Memory / File / ChromaDB run without a server; Redis is exercised with a tiny fake
connection (SCAN / DELETE / JSON.SET) so no Redis Stack is needed.
"""
import fnmatch
import tempfile

import pytest

from blue_data.source.vector.memory_vector_source import MemoryVectorSource
from blue_data.source.vector.file_vector_source import FileVectorSource

EMB = {"embedding": [0.1, 0.2, 0.3, 0.4]}


def _make_chromadb():
    chromadb = pytest.importorskip("chromadb")  # noqa: F841
    from blue_data.source.vector.chromadb.chromadb_vector_source import ChromaDBVectorSource
    return ChromaDBVectorSource("v")


@pytest.fixture(params=["memory", "file", "chromadb"])
def vs(request):
    if request.param == "memory":
        return MemoryVectorSource("v")
    if request.param == "file":
        return FileVectorSource("v", directory=tempfile.mkdtemp())
    return _make_chromadb()


def _seed(vs, collection, page, n):
    vs.create_index(f"{collection}_idx", collection, dim=4)
    for i in range(n):
        vs.upsert(collection, f"{page}_{i:04d}", dict(EMB))


# ---------- list_ids ----------

def test_list_ids_all_and_by_prefix(vs):
    _seed(vs, "docs", "pageA", 3)
    _seed(vs, "docs", "pageB", 2)

    assert sorted(vs.list_ids("docs")) == [
        "pageA_0000", "pageA_0001", "pageA_0002", "pageB_0000", "pageB_0001",
    ]
    assert sorted(vs.list_ids("docs", prefix="pageA_")) == [
        "pageA_0000", "pageA_0001", "pageA_0002",
    ]
    assert vs.list_ids("docs", prefix="nope_") == []


# ---------- delete honors the count contract (probe-loop safety) ----------

def test_delete_returns_real_count(vs):
    _seed(vs, "docs", "pageA", 1)
    assert vs.delete("docs", "pageA_0000") == 1
    assert vs.delete("docs", "pageA_0000") == 0   # already gone
    assert vs.delete("docs", "never_there") == 0


# ---------- delete_by_prefix ----------

def test_delete_by_prefix_scoped_and_counted(vs):
    _seed(vs, "docs", "pageA", 3)
    _seed(vs, "docs", "pageB", 2)

    assert vs.delete_by_prefix("docs", "pageA_") == 3
    assert vs.list_ids("docs", prefix="pageA_") == []
    assert sorted(vs.list_ids("docs")) == ["pageB_0000", "pageB_0001"]  # other page intact
    assert vs.delete_by_prefix("docs", "pageA_") == 0                    # idempotent


# ---------- the "Done when": a shrunk page leaves no stale chunks, no freshness store ----------

def test_reingested_shrink_leaves_no_stale_chunks(vs):
    _seed(vs, "docs", "page", 5)             # first ingest: 5 chunks
    new_count = 3                            # re-ingest produces fewer
    # State-free cleanup: enumerate the page's chunks and drop any at index >= new_count.
    stale = [cid for cid in vs.list_ids("docs", prefix="page_")
             if int(cid.rsplit("_", 1)[1]) >= new_count]
    removed = sum(vs.delete("docs", cid) for cid in stale)
    assert removed == 2
    assert sorted(vs.list_ids("docs", prefix="page_")) == ["page_0000", "page_0001", "page_0002"]


# ---------- Redis backend (fake connection, no server) ----------

class _FakeRedis:
    def __init__(self):
        self.store = {}

    def json(self):
        store = self.store

        class _J:
            def set(self, key, path, doc):
                store[key] = doc
                return True
        return _J()

    def scan(self, cursor=0, match="*", count=100):
        return (0, [k for k in list(self.store) if fnmatch.fnmatch(k, match)])

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n


def _redis_vs():
    pytest.importorskip("redis")
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource
    rv = RedisVectorSource("v", properties={"connection": {
        "host": "h", "port": 6379, "db": 0, "scan_prefix": "t139:",
    }})
    rv.connection = _FakeRedis()  # lazy client never contacts a server; swap in the fake
    return rv


def test_redis_list_ids_delete_and_prefix():
    rv = _redis_vs()
    for i in range(3):
        rv.upsert("docs", f"pageA_{i:04d}", dict(EMB))
    rv.upsert("docs", "pageB_0000", dict(EMB))

    assert sorted(rv.list_ids("docs", prefix="pageA_")) == ["pageA_0000", "pageA_0001", "pageA_0002"]
    assert rv.delete("docs", "pageA_0000") == 1
    assert rv.delete("docs", "pageA_0000") == 0
    assert rv.delete_by_prefix("docs", "pageA_") == 2        # the two remaining pageA chunks
    assert rv.list_ids("docs", prefix="pageA_") == []
    assert rv.list_ids("docs") == ["pageB_0000"]             # other page intact
