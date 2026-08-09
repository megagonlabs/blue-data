"""Integration tests for RedisStreamSource.

Requires a running Redis instance. Auto-skipped when unavailable.

Default connection: localhost:6379, db=15 (to avoid polluting real data).
Override via: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD.

Run just these tests:
    python3 -m pytest lib/tests/integration/test_redis_stream_source.py -v
"""
import os
import uuid

import pytest

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _redis_kwargs():
    return {
        "host":     os.environ.get("REDIS_HOST", "localhost"),
        "port":     int(os.environ.get("REDIS_PORT", "6379")),
        "db":       15,
        "password": os.environ.get("REDIS_PASSWORD") or None,
        "decode_responses": True,
    }


def _redis_available():
    if redis_lib is None:
        return False
    try:
        r = redis_lib.Redis(**_redis_kwargs())
        r.ping()
        return True
    except Exception:
        return False


skip_no_redis = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis not available — set REDIS_HOST/REDIS_PORT or start a local server",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def raw_conn():
    """Raw Redis connection on db=15 for setup/teardown."""
    r = redis_lib.Redis(**_redis_kwargs())
    yield r
    r.close()


@pytest.fixture
def stream_name(raw_conn):
    """Unique stream key, deleted after each test."""
    name = f"test_stream_{uuid.uuid4().hex[:12]}"
    yield name
    raw_conn.delete(name)


@pytest.fixture
def src(raw_conn):
    """RedisStreamSource on db=15."""
    from blue_data.source.stream.redis.redis_stream_source import RedisStreamSource
    source = RedisStreamSource(
        "test_redis_stream",
        properties={
            "connection": {
                "host": os.environ.get("REDIS_HOST", "localhost"),
                "port": int(os.environ.get("REDIS_PORT", "6379")),
                "db": 15,
                "password": os.environ.get("REDIS_PASSWORD") or None,
            }
        },
    )
    return source


# ---------------------------------------------------------------------------
# publish / consume
# ---------------------------------------------------------------------------

@skip_no_redis
def test_publish_and_consume_one(src, stream_name):
    src.publish(stream_name, {"key": "value"})
    messages = src.consume(stream_name, count=1)
    assert len(messages) == 1
    assert messages[0]["key"] == "value"


@skip_no_redis
def test_consume_advances_cursor(src, stream_name):
    src.publish(stream_name, {"n": "1"})
    src.publish(stream_name, {"n": "2"})
    first = src.consume(stream_name, count=1)
    second = src.consume(stream_name, count=1)
    assert first[0]["n"] == "1"
    assert second[0]["n"] == "2"


@skip_no_redis
def test_consume_empty_stream_returns_empty(src, stream_name):
    # stream doesn't exist yet
    result = src.consume(stream_name, count=5)
    assert result == []


@skip_no_redis
def test_consume_count_limits_results(src, stream_name):
    for i in range(5):
        src.publish(stream_name, {"i": str(i)})
    messages = src.consume(stream_name, count=3)
    assert len(messages) == 3


@skip_no_redis
def test_consume_all_messages(src, stream_name):
    for i in range(4):
        src.publish(stream_name, {"i": str(i)})
    all_msgs = src.consume(stream_name, count=10)
    assert len(all_msgs) == 4


@skip_no_redis
def test_consume_returns_message_id(src, stream_name):
    src.publish(stream_name, {"x": "1"})
    messages = src.consume(stream_name, count=1)
    assert "_id" in messages[0]


@skip_no_redis
def test_consume_no_duplicates(src, stream_name):
    src.publish(stream_name, {"v": "a"})
    src.publish(stream_name, {"v": "b"})
    batch1 = src.consume(stream_name, count=2)
    batch2 = src.consume(stream_name, count=2)
    ids1 = {m["_id"] for m in batch1}
    ids2 = {m["_id"] for m in batch2}
    assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Multiple streams
# ---------------------------------------------------------------------------

@skip_no_redis
def test_multiple_streams_independent(src, raw_conn):
    s1 = f"stream_a_{uuid.uuid4().hex[:8]}"
    s2 = f"stream_b_{uuid.uuid4().hex[:8]}"
    try:
        src.publish(s1, {"src": "a"})
        src.publish(s2, {"src": "b"})
        m1 = src.consume(s1, count=1)
        m2 = src.consume(s2, count=1)
        assert m1[0]["src"] == "a"
        assert m2[0]["src"] == "b"
    finally:
        raw_conn.delete(s1)
        raw_conn.delete(s2)


# ---------------------------------------------------------------------------
# delete_stream
# ---------------------------------------------------------------------------

@skip_no_redis
def test_delete_stream_removes_key(src, stream_name, raw_conn):
    src.publish(stream_name, {"x": "1"})
    src.delete_stream(stream_name)
    assert raw_conn.exists(stream_name) == 0


@skip_no_redis
def test_delete_stream_clears_cursor(src, stream_name):
    src.publish(stream_name, {"x": "1"})
    src.consume(stream_name, count=1)
    src.delete_stream(stream_name)
    assert stream_name not in src._cursors


@skip_no_redis
def test_delete_missing_stream_no_error(src, stream_name):
    src.delete_stream("nonexistent_stream_xyz")  # should not raise


# ---------------------------------------------------------------------------
# create_stream
# ---------------------------------------------------------------------------

@skip_no_redis
def test_create_stream_returns_success(src, stream_name):
    result = src.create_stream(stream_name)
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Message field passthrough
# ---------------------------------------------------------------------------

@skip_no_redis
def test_message_with_multiple_fields(src, stream_name):
    src.publish(stream_name, {"user_id": "42", "action": "click", "ts": "100"})
    messages = src.consume(stream_name, count=1)
    assert messages[0]["user_id"] == "42"
    assert messages[0]["action"] == "click"
    assert messages[0]["ts"] == "100"
