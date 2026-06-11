"""End-to-end tests for DataRegistry.sync_source.

Uses SQLiteDBSource (no external deps) backed by MemoryJSONSource for the
registry store.  A Redis-backend variant is included and auto-skipped when
Redis is unavailable.

Fixtures create SQLite .db files directly (bypassing the registry create
helpers) so sync_source is genuinely discovering schema from a live source
rather than replaying what we already registered.
"""
import hashlib
import math
import os
import sqlite3

import pytest

from registry.data_registry import DataRegistry
from source.json.memory_json_source import MemoryJSONSource
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from source.vector.memory_vector_source import MemoryVectorSource

# ---------- helpers ----------

VECTOR_DIM = 64
HYBRID_CONFIG = {"vector_threshold": 0.0, "combined_threshold": 0.0}


def _hash_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(VECTOR_DIM)]


def _make_registry(tmp_path, rebuild=False):
    source = SQLiteDBSource(
        name="mydb",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource(),
        embedding_fn=_hash_embedding,
        vector_dim=VECTOR_DIM,
        rebuild=rebuild,
        hybrid_config=HYBRID_CONFIG,
    )
    reg.register_source(source)
    return reg


def _create_db(tmp_path, db_name: str, ddl: list[str]) -> str:
    """Create a SQLite .db file with the given DDL statements."""
    path = os.path.join(str(tmp_path), db_name + ".db")
    conn = sqlite3.connect(path)
    for stmt in ddl:
        conn.execute(stmt)
    conn.commit()
    conn.close()
    return path


def _insert_rows(tmp_path, db_name: str, sql: str):
    path = os.path.join(str(tmp_path), db_name + ".db")
    conn = sqlite3.connect(path)
    conn.execute(sql)
    conn.commit()
    conn.close()


# ---------- fixtures ----------

@pytest.fixture
def tmp_reg(tmp_path):
    return _make_registry(tmp_path), tmp_path


@pytest.fixture
def tmp_reg_with_search(tmp_path):
    return _make_registry(tmp_path, rebuild=True), tmp_path


# ---------- basic discovery ----------

def test_sync_discovers_databases(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"])
    _create_db(tmp_path, "hr", ["CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT)"])

    reg.sync_source("mydb", recursive=True)

    db_names = [r["name"] for r in reg.list_source_databases("mydb")]
    assert "sales" in db_names
    assert "hr" in db_names


def test_sync_registers_collection(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])

    reg.sync_source("mydb", recursive=True)

    collections = [r["name"] for r in reg.list_database_collections("mydb", "sales")]
    assert "public" in collections


def test_sync_recursive_registers_entities(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)",
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT)",
    ])

    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "orders" in entities
    assert "customers" in entities


def test_sync_recursive_registers_attributes(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL, status TEXT)"
    ])

    reg.sync_source("mydb", recursive=True)

    attrs = [r["name"] for r in reg.list_entity_attributes("mydb", "sales", "public", "orders")]
    assert "id" in attrs
    assert "total" in attrs
    assert "status" in attrs


def test_sync_stores_attribute_type(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"
    ])

    reg.sync_source("mydb", recursive=True)

    attrs = reg.list_entity_attributes("mydb", "sales", "public", "orders")
    attr_map = {a["name"]: a for a in attrs}
    assert attr_map["id"]["properties"].get("info", {}).get("type", "").upper() in {"INTEGER", "INT"}


# ---------- incremental sync ----------

def test_sync_picks_up_new_database(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])
    reg.sync_source("mydb", recursive=True)

    _create_db(tmp_path, "analytics", ["CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT)"])
    reg.sync_source("mydb", recursive=True)

    db_names = [r["name"] for r in reg.list_source_databases("mydb")]
    assert "analytics" in db_names
    assert "sales" in db_names


def test_sync_picks_up_new_table(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])
    reg.sync_source("mydb", recursive=True)

    db_path = os.path.join(str(tmp_path), "sales.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
    conn.commit()
    conn.close()

    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "products" in entities
    assert "orders" in entities


def test_sync_removes_dropped_database(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])
    _create_db(tmp_path, "staging", ["CREATE TABLE temp (id INTEGER PRIMARY KEY)"])

    reg.sync_source("mydb", recursive=True)
    db_names_before = [r["name"] for r in reg.list_source_databases("mydb")]
    assert "staging" in db_names_before

    os.remove(os.path.join(str(tmp_path), "staging.db"))
    reg.sync_source("mydb", recursive=True)

    db_names_after = [r["name"] for r in reg.list_source_databases("mydb")]
    assert "staging" not in db_names_after
    assert "sales" in db_names_after


def test_sync_removes_dropped_table(tmp_reg):
    reg, tmp_path = tmp_reg
    db_path = _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY)",
        "CREATE TABLE temp_table (id INTEGER PRIMARY KEY)",
    ])
    reg.sync_source("mydb", recursive=True)
    entities_before = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "temp_table" in entities_before

    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE temp_table")
    conn.commit()
    conn.close()

    reg.sync_source("mydb", recursive=True)

    entities_after = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "temp_table" not in entities_after
    assert "orders" in entities_after


# ---------- idempotency ----------

def test_sync_idempotent_no_duplicate_databases(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])

    reg.sync_source("mydb", recursive=True)
    reg.sync_source("mydb", recursive=True)
    reg.sync_source("mydb", recursive=True)

    db_names = [r["name"] for r in reg.list_source_databases("mydb")]
    assert db_names.count("sales") == 1


def test_sync_idempotent_no_duplicate_entities(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"])

    reg.sync_source("mydb", recursive=True)
    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert entities.count("orders") == 1


def test_sync_idempotent_no_duplicate_attributes(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"])

    reg.sync_source("mydb", recursive=True)
    reg.sync_source("mydb", recursive=True)

    attrs = [r["name"] for r in reg.list_entity_attributes("mydb", "sales", "public", "orders")]
    assert attrs.count("id") == 1
    assert attrs.count("total") == 1


# ---------- error handling ----------

def test_sync_unregistered_source_raises(tmp_path):
    reg = DataRegistry(store=MemoryJSONSource())
    with pytest.raises(ValueError, match="not registered"):
        reg.sync_source("ghost")


# ---------- stats collection after sync ----------

def test_collect_entity_stats_after_sync(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"
    ])
    _insert_rows(tmp_path, "sales", "INSERT INTO orders VALUES (1, 99.9)")
    _insert_rows(tmp_path, "sales", "INSERT INTO orders VALUES (2, 49.5)")

    reg.sync_source("mydb", recursive=True)
    stats = reg.collect_source_database_collection_entity_stats("mydb", "sales", "public", "orders")

    assert stats["row_count"] == 2


def test_collect_database_stats_after_sync(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])

    reg.sync_source("mydb", recursive=True)
    stats = reg.collect_source_database_stats("mydb", "sales")

    assert "size_bytes" in stats
    assert stats.get("table_count", 0) >= 1


def test_stats_stored_on_record_after_collection(tmp_reg):
    reg, tmp_path = tmp_reg
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])
    _insert_rows(tmp_path, "sales", "INSERT INTO orders VALUES (1)")

    reg.sync_source("mydb", recursive=True)
    reg.collect_source_database_collection_entity_stats("mydb", "sales", "public", "orders")

    stored = reg.get_source_database_collection_entity_property(
        "mydb", "sales", "public", "orders", "stats"
    )
    assert stored is not None
    assert stored["row_count"] == 1


# ---------- full pipeline (sync → stats → search) ----------

def test_entities_searchable_after_sync(tmp_reg_with_search):
    reg, tmp_path = tmp_reg_with_search
    _create_db(tmp_path, "sales", [
        "CREATE TABLE customer_orders (id INTEGER PRIMARY KEY, amount REAL)",
        "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)",
    ])

    reg.sync_source("mydb", recursive=True)

    results = reg.search_records("customer orders")
    names = [r["name"] for r in results]
    assert "customer_orders" in names


# ---------- Redis backend variant ----------

TEST_DB = 15
TEST_NS = "test_sync_source"
TEST_VEC_PREFIX = "test_sync_source_vec"
TEST_INDEX = "test_sync_source_index"


@pytest.fixture(scope="module")
def redis_conn():
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(autouse=False)
def flush_redis(redis_conn):
    _flush_redis(redis_conn)
    yield
    _flush_redis(redis_conn)


def _flush_redis(r):
    for pattern in [f"{TEST_NS}:*", f"{TEST_VEC_PREFIX}:*"]:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break


@pytest.fixture
def redis_registry(tmp_path, redis_conn, flush_redis):
    import redis as redis_lib
    from source.json.redis.redis_json_source import RedisJSONSource
    from source.vector.redis.redis_vector_source import RedisVectorSource

    json_conn = redis_lib.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=True)
    vec_conn = redis_lib.Redis(host="localhost", port=6379, db=TEST_DB, decode_responses=False)

    store = RedisJSONSource(connection=json_conn, properties={"namespace": TEST_NS})
    vector_source = RedisVectorSource(
        name="test_vec",
        properties={"connection": {
            "host": "localhost", "port": 6379, "db": TEST_DB,
            "scan_prefix": TEST_VEC_PREFIX,
        }},
    )
    vector_source.connection = vec_conn

    source = SQLiteDBSource(
        name="mydb",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )

    reg = DataRegistry(
        store=store,
        vector_source=vector_source,
        embedding_fn=_hash_embedding,
        vector_dim=VECTOR_DIM,
        index_name=TEST_INDEX,
        rebuild=True,
        hybrid_config=HYBRID_CONFIG,
    )
    reg.register_source(source)
    return reg, tmp_path


def test_redis_sync_discovers_entities(redis_registry):
    reg, tmp_path = redis_registry
    _create_db(tmp_path, "sales", [
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)",
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT)",
    ])

    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "orders" in entities
    assert "customers" in entities


def test_redis_sync_idempotent(redis_registry):
    reg, tmp_path = redis_registry
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])

    reg.sync_source("mydb", recursive=True)
    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert entities.count("orders") == 1


def test_redis_sync_incremental_new_table(redis_registry):
    reg, tmp_path = redis_registry
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY)"])
    reg.sync_source("mydb", recursive=True)

    db_path = os.path.join(str(tmp_path), "sales.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

    reg.sync_source("mydb", recursive=True)

    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "orders" in entities
    assert "products" in entities


def test_redis_sync_entities_searchable(redis_registry):
    reg, tmp_path = redis_registry
    _create_db(tmp_path, "sales", [
        "CREATE TABLE customer_orders (id INTEGER PRIMARY KEY, amount REAL)",
    ])

    reg.sync_source("mydb", recursive=True)

    results = reg.search_records("customer orders")
    names = [r["name"] for r in results]
    assert "customer_orders" in names


def test_redis_collect_stats_after_sync(redis_registry):
    reg, tmp_path = redis_registry
    _create_db(tmp_path, "sales", ["CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)"])
    _insert_rows(tmp_path, "sales", "INSERT INTO orders VALUES (1, 100.0)")
    _insert_rows(tmp_path, "sales", "INSERT INTO orders VALUES (2, 200.0)")

    reg.sync_source("mydb", recursive=True)
    stats = reg.collect_source_database_collection_entity_stats("mydb", "sales", "public", "orders")

    assert stats["row_count"] == 2

    stored = reg.get_source_database_collection_entity_property(
        "mydb", "sales", "public", "orders", "stats"
    )
    assert stored["row_count"] == 2
