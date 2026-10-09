"""#89 — writes/DDL without commit=True must be blocked before they run, not
rolled back after (SQLite DDL auto-commits). Covered here on SQLite; Postgres
and MySQL use the same base guard with dialect read-only hooks."""
import sqlite3

import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def src(tmp_path):
    s = SQLiteDBSource(name="g", properties={"connection": {"database_directory": str(tmp_path)}})
    s.create_database("db", overwrite=True)
    s.create_database_collection_entity(
        "db", "public", "t",
        properties={"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]},
        overwrite=True,
    )
    s.execute_query("INSERT INTO t VALUES (1)", database="db", optional_properties={"commit": True})
    return s


def _tables(src):
    path = src._get_database_path("db")
    con = sqlite3.connect(path)
    try:
        return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    finally:
        con.close()


def test_drop_without_commit_is_blocked(src):
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query("DROP TABLE t", database="db")
    assert "t" in _tables(src)


def test_delete_without_commit_is_blocked(src):
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query("DELETE FROM t", database="db")
    assert src.execute_query("SELECT COUNT(*) AS n FROM t", database="db")[0]["n"] == 1


def test_multi_statement_without_commit_rejected(src):
    with pytest.raises(ValueError, match="(?i)multiple|commit=True"):
        src.execute_query("DROP TABLE t; SELECT 1", database="db")
    assert "t" in _tables(src)


def test_select_without_commit_still_works(src):
    assert src.execute_query("SELECT id FROM t", database="db") == [{"id": 1}]


def test_drop_with_commit_succeeds(src):
    src.execute_query("DROP TABLE t", database="db", optional_properties={"commit": True})
    assert "t" not in _tables(src)
