"""Regression tests for issue #211.

build_store() / build_vector_source() parsed BLUE_DATA_REGISTRY_REDIS_URL but kept only
host/port/db, dropping the username, password, the rediss:// (TLS) scheme and query
options — so a password-protected or TLS Redis could not back the registry or its vector
source. The URL is now carried through and the source authenticates via
redis.Redis.from_url. The sources also accept discrete connection.username / ssl.

No live server: redis.Redis / .from_url build the client lazily (connects on first
command), so we inspect connection_pool kwargs and the connection class directly.
"""
import json

import pytest

redis = pytest.importorskip("redis")

from blue_data.config import build_store, build_vector_source
from blue_data.registry.data_registry import _sanitize_properties

URL = "redis://myuser:placeholder-pw@127.0.0.1:46480/2"   # placeholder, not a real secret
TLS_URL = "rediss://user:pw@redis.example:6380/0"


def _kwargs(client):
    return client.connection_pool.connection_kwargs


# ---------- build_store ----------

def test_build_store_carries_url_credentials(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_REDIS_URL", URL)

    store = build_store()
    conn = store.properties["connection"]
    assert conn["url"] == URL
    assert conn["username"] == "myuser"

    ref = _kwargs(redis.Redis.from_url(URL))
    got = _kwargs(store.connection)
    for key in ("host", "port", "db", "username", "password"):
        assert got.get(key) == ref.get(key), key
    assert got["password"] == "placeholder-pw"


def test_build_store_tls_scheme(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_REDIS_URL", TLS_URL)

    store = build_store()
    assert store.properties["connection"]["ssl"] is True
    # rediss:// must produce an SSL connection, exactly as from_url does.
    assert store.connection.connection_pool.connection_class is \
        redis.Redis.from_url(TLS_URL).connection_pool.connection_class
    assert store.connection.connection_pool.connection_class.__name__ == "SSLConnection"


# ---------- build_vector_source ----------

def test_build_vector_source_carries_url_credentials(monkeypatch):
    # RediSearch builds indexes only on db 0 (#215), so the vector source must use db 0;
    # the credentials still have to survive URL parsing.
    url0 = "redis://myuser:placeholder-pw@127.0.0.1:46480/0"
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_REDIS_URL", url0)
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "redis")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SCAN_PREFIX", "t211_vec:")

    vs = build_vector_source(embedding_fn=lambda t: [0.0] * 4)
    conn = vs.properties["connection"]
    assert conn["url"] == url0
    assert conn["scan_prefix"] == "t211_vec:"   # URL parsing must not drop the prefix

    got = _kwargs(vs.connection)
    assert got["password"] == "placeholder-pw"
    assert got["db"] == 0


# ---------- source-level: url and discrete username/ssl ----------

def test_redis_json_source_url_authenticates_like_from_url():
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource

    src = RedisJSONSource(properties={"connection": {"url": URL}})
    ref = _kwargs(redis.Redis.from_url(URL))
    got = _kwargs(src.connection)
    for key in ("host", "port", "db", "username", "password"):
        assert got.get(key) == ref.get(key), key


def test_redis_json_source_discrete_username_and_ssl():
    from blue_data.source.json.redis.redis_json_source import RedisJSONSource

    src = RedisJSONSource(properties={"connection": {
        "host": "h", "port": 6380, "db": 1,
        "username": "u", "password": "placeholder-pw", "ssl": True,
    }})
    got = _kwargs(src.connection)
    assert got["username"] == "u"
    assert got["password"] == "placeholder-pw"
    assert src.connection.connection_pool.connection_class.__name__ == "SSLConnection"


# ---------- the password is not persisted ----------

def test_sanitizer_strips_url_password():
    clean = _sanitize_properties({"connection": {"url": URL, "username": "myuser"}})
    assert "placeholder-pw" not in json.dumps(clean)
    assert clean["connection"]["url"] == "redis://myuser@127.0.0.1:46480/2"  # userinfo pw stripped
    assert clean["connection"]["username"] == "myuser"                        # non-secret kept
