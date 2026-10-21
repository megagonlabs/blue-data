"""#110 — exercise the DataSource conformance kit (blue_data.testing.conformance):
prove blue-data's own sources pass it, and that it actually catches the contract
violations the cross-repo review found (async-over-sync override, wrong
execute_query_nl signature)."""
import sqlite3

import pytest

from blue_data.testing.conformance import DataSourceConformance
from blue_data.source.source import DataSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.graph.memory_graph_source import MemoryGraphSource


# ---------- the kit runs green against blue-data's own sources ----------

class TestSQLiteConformance(DataSourceConformance):
    @pytest.fixture
    def data_source(self, tmp_path):
        c = sqlite3.connect(tmp_path / "shop.db")
        c.execute("create table orders(id int)")
        c.executemany("insert into orders values(?)", [(1,), (2,)])
        c.commit(); c.close()
        return SQLiteDBSource(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})

    @pytest.fixture
    def sample_query(self):
        return ("select count(*) as n from orders", {"database": "shop"})


class TestMemoryGraphConformance(DataSourceConformance):
    @pytest.fixture
    def data_source(self):
        return MemoryGraphSource("g")  # structural checks only (no sample_query)


# ---------- the kit catches real contract violations ----------

class _AsyncOverrideSource(DataSource):
    """Violates §6: overrides a sync base method with async def (kb's pattern)."""
    def __init__(self):
        super().__init__("bad_async", properties={"connection": {"protocol": "stub"}})

    async def fetch_database_schema(self, database):  # sync in the base
        return {}


class _BadNLSignatureSource(DataSource):
    """Violates §2: execute_query_nl renames query -> text, drops kwargs (web's pattern)."""
    def __init__(self):
        super().__init__("bad_nl", properties={"connection": {"protocol": "stub"}})

    def execute_query_nl(self, text, collection=None):
        return []


def test_kit_flags_async_override_of_sync_method():
    with pytest.raises(AssertionError, match="async overrides"):
        DataSourceConformance().test_no_async_override_of_sync_base_methods(_AsyncOverrideSource())


def test_kit_flags_wrong_execute_query_nl_signature():
    with pytest.raises(AssertionError, match="execute_query_nl"):
        DataSourceConformance().test_execute_query_nl_accepts_registry_signature(_BadNLSignatureSource())
