"""#270: `source query` rendered rows through the record formatter, so the default
table format printed ``?  ?`` for every row and ``nl`` kept only a ``name`` column.
Query results are now rendered as a column table (``table``), as ``key=value`` pairs
keeping every column (``nl``), and unchanged for ``json``.
"""
import json

from registry_cli.main import cli

Q = "SELECT total, status FROM orders"


def test_table_shows_columns_and_values(runner):
    r = runner.invoke(cli, ["source", "query", "sales", Q, "--database", "prod"])
    assert r.exit_code == 0, r.output
    # real column headers and data — not the record formatter's "?  ?"
    assert "total" in r.output and "status" in r.output
    assert "completed" in r.output and "pending" in r.output
    assert "?  ?" not in r.output


def test_nl_keeps_every_column(runner):
    r = runner.invoke(cli, ["--format", "nl", "source", "query", "sales", Q, "--database", "prod"])
    assert r.exit_code == 0, r.output
    lines = [l for l in r.output.splitlines() if l.strip()]
    assert lines, r.output
    # every column present on each row, as key=value (not just one column)
    for line in lines:
        assert "total=" in line and "status=" in line


def test_nl_keeps_name_column(runner):
    # A row with a `name` column used to print only its value; now it keeps all columns.
    r = runner.invoke(cli, ["--format", "nl", "source", "query", "sales",
                            "SELECT 1 AS id, 'x' AS name", "--database", "prod"])
    assert r.exit_code == 0, r.output
    assert "id=1" in r.output and "name=x" in r.output


def test_json_unchanged(runner):
    r = runner.invoke(cli, ["--format", "json", "source", "query", "sales", Q, "--database", "prod"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert isinstance(data, list) and data
    assert set(data[0]) == {"total", "status"}


def test_single_column_aggregate(runner):
    r = runner.invoke(cli, ["source", "query", "sales",
                            "SELECT count(*) AS n FROM orders", "--database", "prod"])
    assert r.exit_code == 0, r.output
    assert "n" in r.output and "2" in r.output
    assert "?" not in r.output
