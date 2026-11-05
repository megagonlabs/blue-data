"""#266 — the read-only guard must classify a statement *before* it runs.

The old guard ran the statement under a read-only session and only refused it
afterwards when no result set came back. That is too late for any statement that
acts outside the transaction — Postgres ``COPY … TO`` writes a server file, ``SET``
changes session/global state, MySQL ``SELECT … INTO OUTFILE`` writes a file, SQLite
``PRAGMA x=`` rewrites the database file — all of which had already taken effect by
the time "refused" was reported. The guard is now deny-by-default and classifies up
front, so a non-read statement never reaches the server.

Classification is dialect-agnostic text analysis (base ``SQLSource``); the SQLite
source is used only because it is the concrete subclass with no external server.
"""
import os
import sqlite3

import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def src(tmp_path):
    s = SQLiteDBSource("g", {"connection": {"database_directory": str(tmp_path)}})
    s.create_database("db", overwrite=True)
    s.create_database_collection_entity(
        "db", "public", "t",
        properties={"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]},
        overwrite=True,
    )
    s.execute_query("INSERT INTO t VALUES (1)", database="db", optional_properties={"commit": True})
    return s


# --- classifier: side-effecting statements refused before execution ---

@pytest.mark.parametrize("stmt", [
    "COPY (SELECT 1) TO '/tmp/x.csv'",          # Postgres server-side file write
    "COPY t FROM '/tmp/x.csv'",                 # Postgres server-side file read
    "SET GLOBAL general_log = 1",               # MySQL global state
    "SET search_path TO public",                # Postgres session state
    "CALL some_proc()",                         # stored procedure
    "DO $$ BEGIN PERFORM 1; END $$",            # Postgres anonymous block
    "LOAD 'x.so'",                              # MySQL plugin load
    "PRAGMA journal_mode=WAL",                  # SQLite pragma assignment
    "VACUUM",                                   # DB-wide rewrite
    "ATTACH DATABASE '/tmp/x.db' AS y",         # external file
    "SELECT 1 INTO OUTFILE '/tmp/x'",           # write disguised as a SELECT
    "select * into dumpfile '/tmp/x' from t",   # lower-case variant
    "INSERT INTO t VALUES (2)",                 # plain DML
    "DROP TABLE t",                             # DDL
])
def test_non_read_statement_refused(src, stmt):
    with pytest.raises(ValueError, match="commit=True"):
        src._assert_read_only_statement(stmt, "Write query executed without commit=True.")


def test_comment_cannot_hide_the_verb(src):
    # A leading comment must not smuggle a write past the leading-keyword check.
    for stmt in ("/* read */ COPY (SELECT 1) TO '/tmp/x'", "-- note\nDELETE FROM t"):
        with pytest.raises(ValueError, match="commit=True"):
            src._assert_read_only_statement(stmt, "Write query executed without commit=True.")


# --- classifier: genuine reads are allowed ---

@pytest.mark.parametrize("stmt", [
    "SELECT id FROM t",
    "  select id from t",
    "(SELECT id FROM t)",
    "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
    "EXPLAIN SELECT id FROM t",
    "SHOW TABLES",
    "VALUES (1), (2)",
    "/* comment */ SELECT 1",
])
def test_read_statement_allowed(src, stmt):
    src._assert_read_only_statement(stmt, "msg")  # must not raise


# --- end-to-end: the side effect never lands (not just the error) ---

def test_pragma_assignment_does_not_change_the_database(src):
    # PRAGMA query_only=ON blocks table writes but NOT `PRAGMA journal_mode=WAL`,
    # which rewrites the database file. Refused up front, the mode is untouched.
    path = src._get_database_path("db")

    def journal_mode():
        con = sqlite3.connect(path)
        try:
            return con.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            con.close()

    before = journal_mode()
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query("PRAGMA journal_mode=WAL", database="db")
    assert journal_mode() == before


def test_copy_to_file_never_created(src, tmp_path):
    target = tmp_path / "leak.csv"
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query(f"COPY (SELECT 1) TO '{target}'", database="db")
    assert not os.path.exists(target)


def test_reads_still_return_rows_without_commit(src):
    assert src.execute_query("SELECT id FROM t", database="db") == [{"id": 1}]
    assert src.execute_query(
        "WITH x AS (SELECT 1 AS n) SELECT n FROM x", database="db"
    ) == [{"n": 1}]


def test_write_still_succeeds_with_commit(src):
    src.execute_query("INSERT INTO t VALUES (2)", database="db",
                      optional_properties={"commit": True})
    assert src.execute_query("SELECT COUNT(*) AS n FROM t", database="db")[0]["n"] == 2
