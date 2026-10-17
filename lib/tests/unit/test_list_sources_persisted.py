"""#109 (XR-01 / BD-06) — list_sources() must include sources persisted in the
registry store, not just the in-process `self.sources` dict. Platform hosts load
a persisted registry with an empty live dict, so the old behaviour hid every
source and made the MCP/REST `list_sources` return []."""
import os

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.file_json_source import FileJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


def _seed_store(tmp_path):
    store = str(tmp_path / "registry.json")
    db = tmp_path / "sql"; db.mkdir()
    import sqlite3
    c = sqlite3.connect(db / "shop.db")
    c.execute("create table orders(id int)"); c.commit(); c.close()
    reg = DataRegistry(store=FileJSONSource(properties={"connection": {"path": store}}))
    reg.register_source(SQLiteDBSource(name="shop", properties={"connection": {"database_directory": str(db)}}))
    reg.sync_source("shop", recursive=True)
    return store


def test_list_sources_includes_persisted(tmp_path):
    store = _seed_store(tmp_path)
    fresh = DataRegistry(store=FileJSONSource(properties={"connection": {"path": store}}))
    assert fresh.sources == {}           # nothing instantiated yet
    assert fresh.list_sources() == ["shop"]  # but the persisted record is listed


def test_list_sources_unions_live_and_persisted_without_duplicates(tmp_path):
    store = _seed_store(tmp_path)
    fresh = DataRegistry(store=FileJSONSource(properties={"connection": {"path": store}}))
    fresh.connect_source("shop")         # instantiate -> now also live
    assert fresh.list_sources() == ["shop"]  # deduped, not ["shop", "shop"]
