"""Regression tests for issue #292.

#266 classified the statement after a regex removed comments, but that regex disagreed
with the servers: it ended a block comment at the first ``*/`` (Postgres nests them),
stripped ``/*! … */`` (MySQL runs its contents), and treated ``--`` inside a string
literal as a comment. So a refusable statement slipped past the guard, ran, and was
still reported as refused. The guard now tokenises comment- and string-aware.

Classification is pure text analysis, exercised here on lightweight SQLSource subclasses
(Postgres nests comments / standard strings; MySQL runs ``/*!`` / backslash-escapes), and
end-to-end on SQLite where a side effect is observable. No external services.
"""
import sqlite3
import tempfile

import pytest

from blue_data.source.sql.sql_source import SQLSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

MSG = "Write query executed without commit=True."


class _PG(SQLSource):
    _string_backslash_escapes = False  # standard_conforming_strings

    def _db_connect(self, database):  # pragma: no cover - never reached in these tests
        raise RuntimeError("no connect")


class _MY(SQLSource):
    _string_backslash_escapes = True

    def _db_connect(self, database):  # pragma: no cover
        raise RuntimeError("no connect")


def _refused(src, query):
    try:
        src._assert_read_only_statement(query, MSG)
        return False
    except ValueError:
        return True


# ---------- the three bypass routes from the report are now refused ----------

@pytest.mark.parametrize("query", [
    "COPY (SELECT 1) TO '/tmp/bd-plain.txt'",                        # control
    "/* /* */ SELECT 1 */ COPY (SELECT 1) TO '/tmp/bd-nested.txt'",  # Postgres nested comment
])
def test_postgres_payloads_refused(query):
    assert _refused(_PG("p"), query)


@pytest.mark.parametrize("query", [
    "SELECT 1 INTO OUTFILE '/x/bd-plain.txt'",                 # control
    "SELECT 1 /*! INTO OUTFILE '/x/bd-versioned.txt' */",      # MySQL executable comment
    "SELECT '--' INTO OUTFILE '/x/bd-dashes.txt'",             # dashes hidden in a string
    "SELECT '\\' INTO OUTFILE '/x/bd-esc.txt'",                # backslash-escaped quote
])
def test_mysql_payloads_refused(query):
    assert _refused(_MY("m"), query)


# ---------- genuine reads, including tricky quoting, stay allowed ----------

@pytest.mark.parametrize("query", [
    "SELECT id FROM t",
    "/* comment */ SELECT 1",
    "-- lead comment\nSELECT 1",
    "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
    "SELECT '-- not a comment' AS note",     # -- inside a string is not a comment
    "SELECT 'a''b' AS s",                     # doubled-quote escape
    "SELECT $$dollar$$ AS d",                 # Postgres dollar quoting
    "(SELECT 1)",
    "EXPLAIN SELECT 1",
])
def test_reads_allowed(query):
    assert not _refused(_PG("p"), query)


# ---------- unterminated / executable comments refuse (refuse when in doubt) ----------

@pytest.mark.parametrize("query", [
    "SELECT 'unterminated",
    "SELECT 1 /* unterminated",
    "SELECT /*+ hint */ 1",     # optimizer-hint comment: body may execute
])
def test_ambiguous_refused(query):
    assert _refused(_MY("m"), query)


# ---------- end to end on SQLite: a comment-hidden write never takes effect ----------

def test_comment_hidden_write_has_no_side_effect():
    d = tempfile.mkdtemp()
    s = SQLiteDBSource("s", {"connection": {"database_directory": d}})
    s.create_database("db", overwrite=True)
    s.create_database_collection_entity(
        "db", "public", "t",
        properties={"cols_definition": [{"name": "id", "type": "INTEGER"}], "primary_key": ["id"]},
        overwrite=True,
    )
    path = s._get_database_path("db")

    def journal_mode():
        con = sqlite3.connect(path)
        try:
            return con.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            con.close()

    before = journal_mode()
    with pytest.raises(ValueError, match="commit=True"):
        s.execute_query("/* note */ PRAGMA journal_mode=WAL", database="db")
    assert journal_mode() == before  # the hidden PRAGMA never ran
    # a read with -- inside a string literal still works
    assert s.execute_query("SELECT '-- x' AS note", database="db") == [{"note": "-- x"}]
