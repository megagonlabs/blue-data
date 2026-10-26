"""Regression tests for issue #177.

On the read-only path, `VACUUM INTO '<path>'` and `ATTACH DATABASE '<path>'` wrote a
file outside database_directory before the post-execution write guard fired
(PRAGMA query_only=ON does not cover ATTACH/VACUUM INTO). A SQLite authorizer now
refuses them at statement-prepare time, before anything is written.
"""
import os
import sqlite3

import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def source_and_outside_dir(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    conn = sqlite3.connect(str(db_dir / "shop.db"))
    conn.execute("CREATE TABLE t(v)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    outside = tmp_path / "outside"  # sibling of database_directory
    outside.mkdir()

    src = SQLiteDBSource("s", {"connection": {"database_directory": str(db_dir)}})
    return src, outside


def test_vacuum_into_refused_before_writing(source_and_outside_dir):
    src, outside = source_and_outside_dir
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query(f"VACUUM INTO '{outside}/copy.db'", database="shop")
    assert os.listdir(outside) == []


def test_attach_database_refused_before_writing(source_and_outside_dir):
    src, outside = source_and_outside_dir
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query(f"ATTACH DATABASE '{outside}/new.db' AS x", database="shop")
    assert os.listdir(outside) == []


def test_read_only_select_still_works(source_and_outside_dir):
    src, _ = source_and_outside_dir
    assert src.execute_query("SELECT v FROM t", database="shop") == [{"v": 1}]
