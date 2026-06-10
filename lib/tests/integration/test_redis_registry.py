"""
DataRegistry with Redis backends — integration tests.

Requires Redis running on localhost:6379.
Auto-skipped when Redis is unavailable.

Uses db=15 and a unique namespace/scan_prefix to avoid polluting real data.
All keys are flushed before and after each test.
"""
import hashlib
import math

import pytest

TEST_DB = 15
TEST_NAMESPACE = "test_registry"
TEST_SCAN_PREFIX = "test_registry_vec"
TEST_INDEX = "test_registry_index"
DIM = 64


def simple_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def redis_conn():
    """Session-scoped Redis connection — skip entire module if Redis unavailable."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(autouse=True)
def flush_test_keys(redis_conn):
    """Wipe all test keys before and after each test."""
    _flush(redis_conn)
    yield
    _flush(redis_conn)


def _flush(r):
    patterns = [
        f"{TEST_NAMESPACE}:*",
        f"{TEST_SCAN_PREFIX}:*",
    ]
    for pattern in patterns:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break


@pytest.fixture
def registry(redis_conn):
    import redis as redis_lib
    from registry.data_registry import DataRegistry
    from source.json.redis.redis_json_source import RedisJSONSource
    from source.vector.redis.redis_vector_source import RedisVectorSource

    json_conn = redis_lib.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=True)
    vec_conn = redis_lib.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=False)

    store = RedisJSONSource(
        connection=json_conn,
        properties={"namespace": TEST_NAMESPACE},
    )
    vector_source = RedisVectorSource(
        name="test_vec",
        properties={
            "connection": {
                "host": "localhost",
                "port": 6379,
                "db": TEST_DB,
                "scan_prefix": TEST_SCAN_PREFIX,
            }
        },
    )
    vector_source.connection = vec_conn

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
    from source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource(connection=redis_conn, properties={"namespace": TEST_NAMESPACE})

    store.set("/source/mydb", {"name": "mydb", "type": "source"})
    result = store.get("/source/mydb")
    assert result == {"name": "mydb", "type": "source"}


def test_redis_json_source_delete(redis_conn):
    from source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource(connection=redis_conn, properties={"namespace": TEST_NAMESPACE})

    store.set("/source/mydb", {"name": "mydb"})
    store.delete("/source/mydb")
    assert store.get("/source/mydb") is None


def test_redis_json_source_root_key(redis_conn):
    from source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource(connection=redis_conn, properties={"namespace": TEST_NAMESPACE})

    store.set("$", {"contents": {"meta": 1}})
    result = store.get("$")
    assert result == {"contents": {"meta": 1}}


def test_redis_json_source_data_property(redis_conn):
    from source.json.redis.redis_json_source import RedisJSONSource
    store = RedisJSONSource(connection=redis_conn, properties={"namespace": TEST_NAMESPACE})

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
    import redis as redis_lib
    from registry.data_registry import DataRegistry
    from source.json.redis.redis_json_source import RedisJSONSource

    conn2 = redis_lib.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=True)
    store2 = RedisJSONSource(connection=conn2, properties={"namespace": TEST_NAMESPACE + "_copy"})
    registry2 = DataRegistry(store=store2)

    try:
        registry2.loads(serialized)
        record = registry2.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
        assert record is not None
        assert record["properties"]["metadata"]["pii"] is True
    finally:
        # clean up the copy namespace
        cursor = 0
        while True:
            cursor, keys = conn2.scan(cursor=cursor, match=f"{TEST_NAMESPACE}_copy:*", count=500)
            if keys:
                conn2.delete(*keys)
            if cursor == 0:
                break
