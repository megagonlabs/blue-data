"""#118 (A) — NL/tool entry points are read-only by default and honor host-pinned
database/collection, so model-generated writes/retargeting can't slip through."""
import pytest

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def src(tmp_path):
    s = SQLiteDBSource(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})
    s.create_database("shop", overwrite=True)
    s.create_database_collection_entity(
        "shop", "public", "throwaway",
        properties={"cols_definition": [{"name": "i", "type": "INTEGER"}], "primary_key": ["i"]},
        overwrite=True,
    )
    return s


def _tables(src):
    return [r["name"] for r in src.execute_query(
        "select name from sqlite_master where type='table'", database="shop")]


def test_nl_query_is_read_only_by_default(src):
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_query_nl("how many rows?", database="shop", llm_fn=lambda p: "DROP TABLE throwaway")
    assert "throwaway" in _tables(src)


def test_nl_tool_execute_query_strips_commit(src):
    with pytest.raises(ValueError, match="commit=True"):
        src.execute_nl_tool(
            "execute_query",
            {"query": "DROP TABLE throwaway", "database": "shop"},
            optional_properties={"commit": True},  # ignored under read_only
        )
    assert "throwaway" in _tables(src)


def test_nl_tool_write_allowed_with_explicit_opt_in(src):
    src.execute_nl_tool(
        "execute_query",
        {"query": "INSERT INTO throwaway VALUES (1)", "database": "shop"},
        optional_properties={"commit": True},
        read_only=False,
    )
    assert len(src.execute_query("SELECT * FROM throwaway", database="shop")) == 1


def test_host_pins_database_over_tool_input(src):
    # tool input points at a non-existent db; the host pin to the real one wins
    result = src.execute_nl_tool(
        "execute_query",
        {"query": "SELECT 1 AS x", "database": "nonexistent"},
        database="shop",
    )
    assert result == [{"x": 1}]
