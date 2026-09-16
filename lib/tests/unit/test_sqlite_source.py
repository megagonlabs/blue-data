"""Unit tests for SQLiteDBSource.

These tests exercise the source directly — no DataRegistry, no server required.
All I/O is in tmp_path so nothing is left on disk after the suite.
"""
import os
import sqlite3

import pandas as pd
import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.file.file_source import FileSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def src(tmp_path):
    return SQLiteDBSource(
        name="test_sqlite",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )


def _create_table(src, db, table, cols=None, rows=None):
    """Create a table and optionally insert rows via execute_query."""
    cols = cols or [
        {"name": "id",   "type": "INTEGER"},
        {"name": "name", "type": "TEXT"},
        {"name": "val",  "type": "REAL"},
    ]
    src.create_database(db, overwrite=True)
    src.create_database_collection_entity(
        db, "public", table,
        properties={"cols_definition": cols, "primary_key": ["id"]},
        overwrite=True,
    )
    for row in (rows or []):
        src.execute_query(row, database=db, optional_properties={"commit": True})


# ===========================================================================
# Initialisation
# ===========================================================================

def test_default_connection_properties(tmp_path):
    src = SQLiteDBSource(name="s", properties={})
    assert src.properties["connection"]["protocol"] == "sql/sqlite"
    assert "database_directory" in src.properties["connection"]


def test_custom_directory(tmp_path):
    src = SQLiteDBSource(
        name="s",
        properties={"connection": {"database_directory": str(tmp_path)}},
    )
    assert src.properties["connection"]["database_directory"] == str(tmp_path)


def test_get_database_path(src, tmp_path):
    path = src._get_database_path("mydb")
    assert path == os.path.join(str(tmp_path), "mydb.db")


def test_get_database_directory_creates_if_missing(tmp_path):
    new_dir = str(tmp_path / "nested" / "dir")
    src = SQLiteDBSource(
        name="s",
        properties={"connection": {"database_directory": new_dir}},
    )
    src._get_database_directory()
    assert os.path.isdir(new_dir)


# ===========================================================================
# fetch_databases
# ===========================================================================

def test_fetch_databases_empty(src):
    assert src.fetch_databases() == []


def test_fetch_databases_lists_db_files(src, tmp_path):
    (tmp_path / "alpha.db").touch()
    (tmp_path / "beta.db").touch()
    dbs = src.fetch_databases()
    assert set(dbs) == {"alpha", "beta"}


def test_fetch_databases_ignores_non_db_files(src, tmp_path):
    (tmp_path / "notes.txt").touch()
    (tmp_path / "archive.tar").touch()
    assert src.fetch_databases() == []


def test_fetch_databases_after_create(src):
    src.create_database("sales")
    assert "sales" in src.fetch_databases()


# ===========================================================================
# create_database
# ===========================================================================

def test_create_database_success(src, tmp_path):
    result = src.create_database("mydb")
    assert result["status"] == "success"
    assert (tmp_path / "mydb.db").exists()


def test_create_database_skips_when_exists(src):
    src.create_database("mydb")
    result = src.create_database("mydb", overwrite=False)
    assert result["status"] == "skipped"


def test_create_database_overwrite(src, tmp_path):
    src.create_database("mydb")
    (tmp_path / "mydb.db").write_bytes(b"old data")
    result = src.create_database("mydb", overwrite=True)
    assert result["status"] == "success"
    # file should be a fresh SQLite database, not the old bytes
    conn = sqlite3.connect(str(tmp_path / "mydb.db"))
    conn.close()


# ===========================================================================
# fetch_database_collections
# ===========================================================================

def test_collections_always_returns_public(src):
    src.create_database("anydb")
    assert src.fetch_database_collections("anydb") == ["public"]


def test_collections_same_regardless_of_tables(src):
    _create_table(src, "mydb", "users")
    assert src.fetch_database_collections("mydb") == ["public"]


# ===========================================================================
# create_database_collection
# ===========================================================================

def test_create_collection_returns_registry_only(src):
    result = src.create_database_collection("mydb", "public")
    assert result["status"] == "registry_only"


# ===========================================================================
# create_database_collection_entity
# ===========================================================================

def test_create_entity_success(src):
    src.create_database("testdb")
    result = src.create_database_collection_entity(
        "testdb", "public", "users",
        properties={
            "cols_definition": [
                {"name": "id",   "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
    )
    assert result["status"] == "success"


def test_create_entity_skips_when_exists(src):
    src.create_database("testdb")
    props = {"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]}
    src.create_database_collection_entity("testdb", "public", "t", properties=props)
    result = src.create_database_collection_entity("testdb", "public", "t", properties=props, overwrite=False)
    assert result["status"] == "skipped"


def test_create_entity_overwrite(src):
    src.create_database("testdb")
    props = {"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]}
    src.create_database_collection_entity("testdb", "public", "t", properties=props)
    result = src.create_database_collection_entity("testdb", "public", "t", properties=props, overwrite=True)
    assert result["status"] == "success"


def test_create_entity_with_primary_key(src, tmp_path):
    src.create_database("testdb", overwrite=True)
    src.create_database_collection_entity(
        "testdb", "public", "orders",
        properties={
            "cols_definition": [
                {"name": "order_id", "type": "INTEGER"},
                {"name": "total",    "type": "REAL"},
            ],
            "primary_key": ["order_id"],
        },
    )
    conn = sqlite3.connect(str(tmp_path / "testdb.db"))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(orders);")
    cols = {row[1]: row for row in cur.fetchall()}
    conn.close()
    assert "order_id" in cols
    assert "total" in cols


def test_create_entity_with_foreign_key(src):
    src.create_database("fkdb")
    src.create_database_collection_entity(
        "fkdb", "public", "customers",
        properties={
            "cols_definition": [{"name": "id", "type": "INTEGER"}],
            "primary_key": ["id"],
        },
    )
    result = src.create_database_collection_entity(
        "fkdb", "public", "orders",
        properties={
            "cols_definition": [
                {"name": "id",          "type": "INTEGER"},
                {"name": "customer_id", "type": "INTEGER"},
            ],
            "primary_key": ["id"],
            "foreign_keys": [{
                "foreign_keys_source_columns": ["customer_id"],
                "foreign_keys_target_columns": ["id"],
                "foreign_keys_target_table": "customers",
            }],
        },
    )
    assert result["status"] == "success"


# ===========================================================================
# fetch_database_collection_entities
# ===========================================================================

def test_fetch_entities_returns_table_names(src):
    _create_table(src, "testdb", "users")
    entities = src.fetch_database_collection_entities("testdb", "public")
    assert "users" in entities


def test_fetch_entities_includes_columns(src):
    _create_table(src, "testdb", "users", cols=[
        {"name": "id",   "type": "INTEGER"},
        {"name": "name", "type": "TEXT"},
    ])
    attrs = src.fetch_database_collection_entities("testdb", "public")["users"]["contents"]["attributes"]
    assert "id" in attrs
    assert "name" in attrs


def test_fetch_entities_column_type_info(src):
    _create_table(src, "testdb", "products", cols=[
        {"name": "id",    "type": "INTEGER"},
        {"name": "price", "type": "REAL"},
    ])
    attrs = src.fetch_database_collection_entities("testdb", "public")["products"]["contents"]["attributes"]
    assert attrs["id"]["info"]["type"] == "INTEGER"
    assert attrs["price"]["info"]["type"] == "REAL"


def test_fetch_entities_empty_database(src):
    src.create_database("empty")
    assert src.fetch_database_collection_entities("empty", "public") == {}


def test_fetch_entities_multiple_tables(src):
    _create_table(src, "testdb", "users")
    src.create_database_collection_entity(
        "testdb", "public", "orders",
        properties={
            "cols_definition": [{"name": "id", "type": "INTEGER"}],
            "primary_key": ["id"],
        },
    )
    entities = src.fetch_database_collection_entities("testdb", "public")
    assert "users" in entities
    assert "orders" in entities


# ===========================================================================
# fetch_database_collection_relations
# ===========================================================================

def test_fetch_relations_always_empty(src):
    _create_table(src, "testdb", "users")
    assert src.fetch_database_collection_relations("testdb", "public") == {}


# ===========================================================================
# execute_query
# ===========================================================================

def test_execute_query_select(src):
    _create_table(src, "testdb", "items", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "val", "type": "TEXT"},
    ], rows=[
        'INSERT INTO items VALUES (1, "hello");',
        'INSERT INTO items VALUES (2, "world");',
    ])
    rows = src.execute_query('SELECT * FROM items ORDER BY id;', database="testdb")
    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[0]["val"] == "hello"


def test_execute_query_requires_database(src):
    with pytest.raises(Exception):
        src.execute_query("SELECT 1;")


def test_execute_query_insert_without_commit_not_persisted(src, tmp_path):
    _create_table(src, "testdb", "t", cols=[{"name": "id", "type": "INTEGER"}])
    # insert without commit flag
    src.execute_query('INSERT INTO t VALUES (99);', database="testdb")
    # open a fresh connection — row should NOT be visible without commit
    conn = sqlite3.connect(str(tmp_path / "testdb.db"))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM t;")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0


def test_execute_query_ops_sql_query(src):
    _create_table(src, "testdb", "items", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "val", "type": "TEXT"},
    ], rows=[
        'INSERT INTO items VALUES (1, "hello");',
        'INSERT INTO items VALUES (2, "world");',
    ])
    rows = src.execute_query(
        {"op": "SQL.QUERY", "query": "SELECT * FROM items ORDER BY id;"},
        database="testdb",
    )
    assert len(rows) == 2
    assert rows[0]["val"] == "hello"


def test_execute_query_ops_fetch_all(src):
    _create_table(src, "testdb", "items", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "val", "type": "TEXT"},
    ], rows=[
        'INSERT INTO items VALUES (1, "hello");',
        'INSERT INTO items VALUES (2, "world");',
    ])
    rows = src.execute_query(
        {"op": "SQL.FETCH_ALL"},
        database="testdb",
        collection="items",
    )
    assert len(rows) == 2


def test_execute_query_ops_unknown_falls_through(src):
    # Unknown ops are passed to the source implementation unchanged.
    # SQLite will raise a driver-level error (not a ValueError from the dispatch layer).
    _create_table(src, "testdb", "t", cols=[{"name": "id", "type": "INTEGER"}])
    with pytest.raises(Exception):
        src.execute_query({"op": "SQL.NONSENSE"}, database="testdb")


# ===========================================================================
# fetch_database_stats
# ===========================================================================

def test_fetch_database_stats_returns_size_and_table_count(src):
    _create_table(src, "testdb", "users")
    stats = src.fetch_database_stats("testdb")
    assert stats["size_bytes"] > 0
    assert stats["table_count"] == 1


def test_fetch_database_stats_multiple_tables(src):
    _create_table(src, "testdb", "a")
    src.create_database_collection_entity(
        "testdb", "public", "b",
        properties={"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]},
    )
    stats = src.fetch_database_stats("testdb")
    assert stats["table_count"] == 2


def test_fetch_database_stats_missing_db_returns_empty(src):
    stats = src.fetch_database_stats("nonexistent")
    assert stats == {}


# ===========================================================================
# fetch_entity_stats
# ===========================================================================

def test_fetch_entity_stats_empty_table(src):
    _create_table(src, "testdb", "users")
    stats = src.fetch_entity_stats("testdb", "public", "users")
    assert stats["row_count"] == 0
    assert stats["row_samples"] == []


def test_fetch_entity_stats_with_rows(src):
    _create_table(src, "testdb", "users", rows=[
        "INSERT INTO users VALUES (1, 'alice', 1.5);",
        "INSERT INTO users VALUES (2, 'bob',   2.5);",
        "INSERT INTO users VALUES (3, 'carol', 3.5);",
    ])
    stats = src.fetch_entity_stats("testdb", "public", "users")
    assert stats["row_count"] == 3
    assert stats["row_sample_size"] == 3
    assert isinstance(stats["row_samples"][0], dict)
    assert "id" in stats["row_samples"][0]


def test_fetch_entity_stats_aligned_flag(src):
    _create_table(src, "testdb", "users", rows=[
        "INSERT INTO users VALUES (1, 'a', 1.0);",
        "INSERT INTO users VALUES (2, 'b', 2.0);",
    ])
    stats = src.fetch_entity_stats("testdb", "public", "users")
    assert stats["row_samples_aligned"] is True


def test_fetch_entity_stats_single_row_not_aligned(src):
    _create_table(src, "testdb", "users", rows=[
        "INSERT INTO users VALUES (1, 'a', 1.0);",
    ])
    stats = src.fetch_entity_stats("testdb", "public", "users")
    assert stats["row_samples_aligned"] is False


# ===========================================================================
# fetch_property_stats
# ===========================================================================

def test_fetch_property_stats_counts(src):
    _create_table(src, "testdb", "users", rows=[
        "INSERT INTO users VALUES (1, 'alice', 10.0);",
        "INSERT INTO users VALUES (2, 'alice', 20.0);",
        "INSERT INTO users VALUES (3, 'carol', 30.0);",
    ])
    stats = src.fetch_property_stats("testdb", "public", "users", "name")
    assert stats["count"] == 3
    assert stats["distinct_count"] == 2
    assert stats["null_count"] == 0


def test_fetch_property_stats_null_count(src):
    src.create_database("testdb")
    src.create_database_collection_entity(
        "testdb", "public", "sparse",
        properties={
            "cols_definition": [
                {"name": "id",  "type": "INTEGER"},
                {"name": "val", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
    )
    for q in [
        "INSERT INTO sparse VALUES (1, 'x');",
        "INSERT INTO sparse VALUES (2, NULL);",
        "INSERT INTO sparse VALUES (3, NULL);",
    ]:
        src.execute_query(q, database="testdb", optional_properties={"commit": True})

    stats = src.fetch_property_stats("testdb", "public", "sparse", "val")
    assert stats["null_count"] == 2
    assert stats["distinct_count"] == 1


def test_fetch_property_stats_sample_values(src):
    _create_table(src, "testdb", "p", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "tag", "type": "TEXT"},
    ], rows=[
        "INSERT INTO p VALUES (1, 'a');",
        "INSERT INTO p VALUES (2, 'b');",
        "INSERT INTO p VALUES (3, 'c');",
    ])
    stats = src.fetch_property_stats("testdb", "public", "p", "tag")
    assert len(stats["sample_values"]) == 3
    assert set(stats["sample_values"]) == {"a", "b", "c"}


def test_fetch_property_stats_min_max_integer(src):
    _create_table(src, "testdb", "nums", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "num", "type": "INTEGER"},
    ], rows=[
        "INSERT INTO nums VALUES (1, 5);",
        "INSERT INTO nums VALUES (2, 15);",
        "INSERT INTO nums VALUES (3, 10);",
    ])
    stats = src.fetch_property_stats("testdb", "public", "nums", "num")
    assert stats["min"] == 5
    assert stats["max"] == 15


def test_fetch_property_stats_min_max_real(src):
    _create_table(src, "testdb", "prices", cols=[
        {"name": "id",    "type": "INTEGER"},
        {"name": "price", "type": "REAL"},
    ], rows=[
        "INSERT INTO prices VALUES (1, 1.5);",
        "INSERT INTO prices VALUES (2, 9.9);",
    ])
    stats = src.fetch_property_stats("testdb", "public", "prices", "price")
    assert stats["min"] == pytest.approx(1.5)
    assert stats["max"] == pytest.approx(9.9)


def test_fetch_property_stats_text_has_no_min_max(src):
    _create_table(src, "testdb", "tags", cols=[
        {"name": "id",  "type": "INTEGER"},
        {"name": "tag", "type": "TEXT"},
    ], rows=["INSERT INTO tags VALUES (1, 'alpha');"])
    stats = src.fetch_property_stats("testdb", "public", "tags", "tag")
    assert stats["min"] is None
    assert stats["max"] is None


def test_fetch_property_stats_most_common_vals(src):
    _create_table(src, "testdb", "t", rows=["INSERT INTO t VALUES (1, 'x', 1.0);"])
    stats = src.fetch_property_stats("testdb", "public", "t", "id")
    assert stats["most_common_vals"] == [(1, 1)]


# ===========================================================================
# import_data
# ===========================================================================

@pytest.fixture
def file_src(tmp_path):
    src = FileSource("files", directory=str(tmp_path / "files"))
    pd.DataFrame([{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]).to_csv(
        tmp_path / "files" / "users.csv", index=False
    )
    return src


def test_import_data_requires_entity(src, file_src):
    src.create_database("db")
    with pytest.raises(ValueError, match="entity"):
        src.import_data(file_src, collection="users", database="db")


def test_import_data_creates_table_and_inserts(src, file_src, tmp_path):
    src.create_database("db")
    result = src.import_data(file_src, collection="users", database="db", entity="users")
    assert result["status"] == "success"
    assert result["rows_imported"] == 2
    rows = src.execute_query('SELECT * FROM "users"', database="db")
    assert len(rows) == 2


def test_import_data_append_adds_rows(src, file_src, tmp_path):
    src.create_database("db")
    src.import_data(file_src, collection="users", database="db", entity="users")
    src.import_data(file_src, collection="users", database="db", entity="users", mode="append")
    rows = src.execute_query('SELECT * FROM "users"', database="db")
    assert len(rows) == 4


def test_import_data_overwrite_truncates(src, file_src, tmp_path):
    src.create_database("db")
    src.import_data(file_src, collection="users", database="db", entity="users")
    src.import_data(file_src, collection="users", database="db", entity="users", mode="overwrite")
    rows = src.execute_query('SELECT * FROM "users"', database="db")
    assert len(rows) == 2


def test_import_data_overwrite_new_table(src, file_src, tmp_path):
    src.create_database("db")
    result = src.import_data(file_src, collection="users", database="db", entity="users", mode="overwrite")
    assert result["rows_imported"] == 2


def test_import_data_empty_source_returns_zero(src, tmp_path):
    src.create_database("db")
    empty_src = FileSource("empty", directory=str(tmp_path / "empty"))
    result = src.import_data(empty_src, collection="users", database="db", entity="users")
    assert result["rows_imported"] == 0


# ---------- fetch_source_stats ----------

def test_fetch_source_stats_empty_directory(tmp_path):
    src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path)}})
    stats = src.fetch_source_stats()
    assert stats["database_count"] == 0
    assert stats["total_size_bytes"] == 0
    assert stats["directory"] == str(tmp_path)


def test_fetch_source_stats_counts_db_files(tmp_path):
    src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path)}})
    src.create_database("alpha")
    src.create_database("beta")
    stats = src.fetch_source_stats()
    assert stats["database_count"] == 2


def test_fetch_source_stats_ignores_non_db_files(tmp_path):
    src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path)}})
    src.create_database("mydb")
    (tmp_path / "readme.txt").write_text("ignore me")
    (tmp_path / "backup.bak").write_text("ignore me too")
    stats = src.fetch_source_stats()
    assert stats["database_count"] == 1


def test_fetch_source_stats_size_increases_after_data_written(tmp_path):
    src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path)}})
    src.create_database("mydb")
    stats_before = src.fetch_source_stats()

    conn = sqlite3.connect(str(tmp_path / "mydb.db"))
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    for i in range(100):
        conn.execute("INSERT INTO users VALUES (?, ?)", (i, "x" * 50))
    conn.commit()
    conn.close()

    stats_after = src.fetch_source_stats()
    assert stats_after["total_size_bytes"] > stats_before["total_size_bytes"]


def test_fetch_source_stats_returns_absolute_directory(tmp_path):
    src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path)}})
    stats = src.fetch_source_stats()
    assert os.path.isabs(stats["directory"])


def test_import_data_e2e_filesource_to_sqlite(tmp_path):
    """CSV file → FileSource → SQLiteDBSource round-trip."""
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    pd.DataFrame([
        {"product": "apple", "price": 1.2},
        {"product": "banana", "price": 0.5},
        {"product": "cherry", "price": 3.0},
    ]).to_csv(files_dir / "products.csv", index=False)

    file_src = FileSource("files", directory=str(files_dir))
    db_src = SQLiteDBSource("db", properties={"connection": {"database_directory": str(tmp_path / "db")}})
    db_src.create_database("shop")

    result = db_src.import_data(file_src, collection="products", database="shop", entity="products")
    assert result["rows_imported"] == 3

    rows = db_src.execute_query('SELECT * FROM "products" ORDER BY price', database="shop")
    assert rows[0]["product"] == "banana"
    assert rows[2]["price"] == 3.0
