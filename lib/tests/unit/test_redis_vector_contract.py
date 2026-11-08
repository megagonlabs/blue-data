"""#113 — RedisVectorSource contract: host/port deprecation shim, idempotent
create_index, TAG-filter escaping, and registry search surviving a missing
vector signal (BM25 fallback instead of a threshold drop). Server-free."""
import pytest

from blue_data.registry.search.hybrid_search import HybridSearch
from blue_data.registry.search.vector_search import VectorSearch, _escape_tag

pytest.importorskip("redis")
from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource


def _rec(name, **extra):
    return {"name": name, "type": "entity", "scope": "/source/s/database/db/collection/public", **extra}


# ---------- TAG escaping ----------

def test_escape_tag_escapes_special_chars():
    assert _escape_tag("/source/shop/entity/orders") == r"\/source\/shop\/entity\/orders"
    assert _escape_tag("a_b1") == "a_b1"  # alphanumerics/underscore untouched


# ---------- host/port deprecation shim ----------

def test_host_port_shim_folds_into_connection(recwarn):
    rv = RedisVectorSource(name="r", host="1.2.3.4", port=6380,
                           properties={"connection": {"scan_prefix": "rv:"}})
    conn = rv.properties["connection"]
    assert conn["host"] == "1.2.3.4" and conn["port"] == 6380
    assert any(issubclass(w.category, DeprecationWarning) for w in recwarn)


def test_unexpected_kwarg_still_raises():
    with pytest.raises(TypeError):
        RedisVectorSource(name="r", bogus=1)


# ---------- scan_prefix is required (#226) ----------

def test_missing_scan_prefix_raises_at_construction():
    with pytest.raises(ValueError, match="scan_prefix"):
        RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1}})


def test_empty_scan_prefix_raises_at_construction():
    with pytest.raises(ValueError, match="scan_prefix"):
        RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": ""}})


def test_platform_scan_prefix_rejected():
    with pytest.raises(ValueError, match="PLATFORM"):
        RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "PLATFORM:x"}})


# ---------- idempotent create_index ----------

def test_create_index_idempotent_on_already_exists():
    rv = RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "x:"}})

    class _Conn:
        def execute_command(self, *a):
            raise Exception("Index already exists")

    rv.connection = _Conn()
    assert rv.create_index("idx", "c", 8) == "OK"  # swallowed, no raise


def test_create_index_reraises_other_errors():
    rv = RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "x:"}})

    class _Conn:
        def execute_command(self, *a):
            raise Exception("some other failure")

    rv.connection = _Conn()
    with pytest.raises(Exception, match="some other failure"):
        rv.create_index("idx", "c", 8)


# ---------- registry search survives no vector signal ----------

class _NoSignalVS(VectorSearch):
    def __init__(self):
        super().__init__(vector_source=None, embedding_fn=lambda t: [1.0, 0.0, 0.0, 0.0])

    def score_record(self, record, query_vector, params):
        return None  # lookup failed / not indexed → no vector signal


def test_hybrid_keeps_bm25_match_when_no_vector_signal():
    cfg = {
        "bm25_weight": 0.3, "vector_weight": 0.7, "value_weight": 0.15,
        "bm25_threshold": 0.0, "vector_threshold": 0.5, "value_threshold": 0.3,
        "combined_threshold": 0.1, "bm25_normalization": "minmax", "enable_schema": False,
        "hierarchical_enabled": False, "search_limit": 1000,
    }
    hs = HybridSearch(config=cfg)
    hs.vector_searcher = _NoSignalVS()
    records = [_rec("orders", description="customer orders"), _rec("zzz", description="unrelated")]
    names = [r["name"] for r in hs.search(records, "orders")]
    assert "orders" in names  # not dropped by vector_threshold despite no vector signal


# ---------- #198: FT.SEARCH must carry LIMIT 0 k ----------

def _knn_cmd(k=None):
    rv = RedisVectorSource(name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": "x:"}})
    query = {"index": "idx", "vector": [0.1, 0.2, 0.3, 0.4]}
    if k is not None:
        query["k"] = k
    return rv._build_knn_command(query)


def test_knn_command_sets_limit_to_k():
    # Without LIMIT, FT.SEARCH returns RediSearch's default of 10 rows whatever k is (#198).
    cmd = _knn_cmd(k=25)
    assert "LIMIT" in cmd
    i = cmd.index("LIMIT")
    assert cmd[i:i + 3] == ["LIMIT", 0, 25]
    # the KNN clause asks for k too
    assert any(isinstance(part, str) and "KNN 25 " in part for part in cmd)


def test_knn_command_limit_defaults_to_default_k():
    cmd = _knn_cmd()  # no k -> default 5
    i = cmd.index("LIMIT")
    assert cmd[i:i + 3] == ["LIMIT", 0, 5]
