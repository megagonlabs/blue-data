"""
DataRegistry with Redis backends — integration tests.

Requires Redis Stack, at localhost:6379 or REDIS_HOST:REDIS_PORT.
Auto-skipped when Redis is unavailable.

Uses db=0 (RediSearch/FT.CREATE only builds indexes on db 0, #215) and a unique
namespace/scan_prefix to avoid polluting real data. Only keys matching that namespace/
prefix are deleted before and after each test (never FLUSHDB).
"""
import hashlib
import math
import os

import pytest

TEST_DB = 0
TEST_NAMESPACE = "test_registry"
TEST_SCAN_PREFIX = "test_registry_vec"
TEST_INDEX = "test_registry_index"
DIM = 64

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


def simple_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def redis_conn():
    """Session-scoped Redis connection — skip entire module if Redis unavailable."""
    try:
        import redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=TEST_DB, decode_responses=True)
        r.ping()
        # Verify Redis Stack (JSON module) is available
        r.json().set("__probe__", "$", {"ok": True})
        r.delete("__probe__")
        return r
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(autouse=True)
def flush_test_keys(redis_conn):
    """Wipe all test keys before and after each test."""
    _flush(redis_conn)
    yield
    _flush(redis_conn)


def _flush_pattern(r, pattern):
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            r.delete(*keys)
        if cursor == 0:
            break


def _flush(r):
    for pattern in [f"{TEST_NAMESPACE}:*", f"{TEST_SCAN_PREFIX}:*"]:
        _flush_pattern(r, pattern)


@pytest.fixture
def registry(redis_conn):
    from blue_data.registry.data_registry import DataRegistry
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    store = RedisJSONSource(
        "test_store",
        properties={
            "namespace": TEST_NAMESPACE,
            "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB},
        },
    )
    vector_source = RedisVectorSource(
        "test_vec",
        properties={
            "connection": {
                "host": REDIS_HOST,
                "port": REDIS_PORT,
                "db": TEST_DB,
                "scan_prefix": TEST_SCAN_PREFIX,
            }
        },
    )

    reg = DataRegistry(
        store=store,
        vector_source=vector_source,
        embedding_fn=simple_embedding,
        vector_dim=DIM,
        index_name=TEST_INDEX,
        rebuild=True,
        hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
    )
    return reg


# ---------- RedisJSONSource unit tests ----------

def test_redis_json_source_set_and_get(redis_conn):
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource("test_store", properties={"namespace": TEST_NAMESPACE, "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB}})

    store.set("/source/mydb", {"name": "mydb", "type": "source"})
    result = store.get("/source/mydb")
    assert result == {"name": "mydb", "type": "source"}


def test_redis_json_source_delete(redis_conn):
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource("test_store", properties={"namespace": TEST_NAMESPACE, "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB}})

    store.set("/source/mydb", {"name": "mydb"})
    store.delete("/source/mydb")
    assert store.get("/source/mydb") is None


def test_redis_json_source_root_key(redis_conn):
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource("test_store", properties={"namespace": TEST_NAMESPACE, "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB}})

    store.set("$", {"contents": {"meta": 1}})
    result = store.get("$")
    assert result == {"contents": {"meta": 1}}


def test_redis_json_source_data_property(redis_conn):
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource("test_store", properties={"namespace": TEST_NAMESPACE, "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB}})

    store.set("$", {"contents": {}})
    store.set("/source/a", {"name": "a"})
    store.set("/source/b", {"name": "b"})

    data = store.data
    assert "$" in data
    assert "/source/a" in data
    assert "/source/b" in data
    assert data["/source/a"] == {"name": "a"}


# ---------- DataRegistry with Redis store ----------

def test_register_and_get_record(registry):
    registry.register_record(
        name="users",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="user accounts",
    )
    record = registry.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
    assert record is not None
    assert record["name"] == "users"
    assert record["description"] == "user accounts"


def test_list_records_from_redis(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.register_record(name="orders", type="entity", scope="/source/mydb/database/prod/collection/public")

    records = registry.list_records()
    names = [r["name"] for r in records]
    assert "users" in names
    assert "orders" in names


def test_update_record_persists_to_redis(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.update_record(
        name="users",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        properties={"metadata": {"owner": "platform-team"}},
    )
    record = registry.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
    assert record["properties"]["metadata"]["owner"] == "platform-team"


def test_deregister_record_removes_from_redis(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.deregister_record("users", "entity", "/source/mydb/database/prod/collection/public")
    assert registry.get_record("users", "entity", "/source/mydb/database/prod/collection/public") is None


# ---------- search with Redis vector backend ----------

def test_search_records_with_redis_vector(registry):
    registry.register_record(
        name="users",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="stores user accounts and profile data",
    )
    registry.register_record(
        name="orders",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="customer purchase orders",
    )

    results = registry.search_records("user accounts")
    assert len(results) > 0
    assert results[0]["name"] == "users"


def test_redis_vector_gives_nonnull_signal(registry):
    # #179: per-record KNN must find the indexed record and return a real vector
    # score — not None (which forced a BM25-only fallback on Redis).
    from blue_data.registry.search.vector_search import VectorSearch
    from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

    scope = "/source/mydb/database/prod/collection/public"
    registry.register_record(
        name="orders", type="entity", scope=scope, description="customer purchase orders"
    )

    vs = RedisVectorSource(
        "probe",
        properties={
            "connection": {
                "host": REDIS_HOST,
                "port": REDIS_PORT,
                "db": TEST_DB,
                "scan_prefix": TEST_SCAN_PREFIX,
            }
        },
    )
    searcher = VectorSearch(
        vector_source=vs, embedding_fn=simple_embedding, index_name=TEST_INDEX, vector_dim=DIM
    )
    rec = {"name": "orders", "type": "entity", "scope": scope}
    score = searcher.score_record(rec, simple_embedding("orders"), {})
    assert score is not None
    assert score == pytest.approx(1.0, abs=0.05)


def test_search_type_filter_with_redis(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb/database/prod/collection/public")
    registry.register_record(name="prod", type="database", scope="/source/mydb")

    results = registry.search_records("users", type="entity")
    assert all(r["type"] == "entity" for r in results)


# ---------- dump / load round-trip ----------

def test_dump_and_load_round_trip(registry):
    registry.register_record(
        name="users",
        type="entity",
        scope="/source/mydb/database/prod/collection/public",
        description="user accounts",
        properties={"metadata": {"pii": True}},
    )

    serialized = registry.dumps()

    # load into a fresh registry backed by a second namespace
    from blue_data.registry.data_registry import DataRegistry
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource

    store2 = RedisJSONSource(
        "test_store_copy",
        properties={
            "namespace": TEST_NAMESPACE + "_copy",
            "connection": {"host": REDIS_HOST, "port": REDIS_PORT, "db": TEST_DB},
        },
    )
    registry2 = DataRegistry(store=store2)

    try:
        registry2.loads(serialized)
        record = registry2.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
        assert record is not None
        assert record["properties"]["metadata"]["pii"] is True
    finally:
        # clean up the copy namespace
        _flush_pattern(store2.connection, f"{TEST_NAMESPACE}_copy:*")


# ---------- #91: special characters in record names ----------

@pytest.mark.parametrize("name", ["sales.v2", "a/b", "$special", "with space", "a.b.c"])
def test_special_char_names_round_trip_redis(registry, name):
    """A dot in a name must not be treated as a JSON sub-path by Redis (#91)."""
    registry.register_record(name=name, type="entity", scope="/source/mydb")

    record = registry.get_record(name, "entity", "/source/mydb")
    assert record is not None
    assert record["name"] == name

    listed = [r["name"] for r in registry.list_records(record_type="entity", scope="/source/mydb")]
    assert listed == [name]


def test_dotted_and_plain_siblings_independent_redis(registry):
    registry.register_record(name="sales", type="database", scope="/source/src")
    registry.register_record(name="sales.v2", type="database", scope="/source/src")

    registry.set_record_property("sales", "database", "/source/src", "stats", {"rows": 1})
    registry.set_record_property("sales.v2", "database", "/source/src", "stats", {"rows": 2})

    databases = sorted(r["name"] for r in registry.list_records(record_type="database", scope="/source/src"))
    assert databases == ["sales", "sales.v2"]

    sales = registry.get_record("sales", "database", "/source/src")
    assert "v2" not in sales
    assert registry.get_record_property("sales", "database", "/source/src", "stats") == {"rows": 1}
    assert registry.get_record_property("sales.v2", "database", "/source/src", "stats") == {"rows": 2}
