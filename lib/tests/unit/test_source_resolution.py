"""#94 — a source persisted by one invocation must be usable by the next:
operational calls resolve the live source from the stored record, not only
from the in-process cache."""
import os
import sqlite3

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.file_json_source import FileJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


def _make_shop_db(dirpath):
    con = sqlite3.connect(os.path.join(dirpath, "shop.db"))
    con.execute("CREATE TABLE orders(id INTEGER)")
    con.commit()
    con.close()


def _file_registry(store_path):
    return DataRegistry(store=FileJSONSource(properties={"connection": {"path": store_path}}))


def test_sync_and_query_resolve_across_invocations(tmp_path):
    store_path = str(tmp_path / "registry.json")
    _make_shop_db(str(tmp_path))

    reg1 = _file_registry(store_path)
    reg1.register_source(
        SQLiteDBSource(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})
    )

    reg2 = _file_registry(store_path)
    assert "shop" in [r["name"] for r in reg2.list_records(record_type="source")]
    assert reg2.get_source("shop") is None

    reg2.sync_source("shop", recursive=True)
    assert "shop" in [d["name"] for d in reg2.list_source_databases("shop")]

    rows = reg2.execute_query("shop", "SELECT 1 AS ok", database="shop")
    assert rows == [{"ok": 1}]


def test_connect_source_rebuilds_and_caches(tmp_path):
    store_path = str(tmp_path / "registry.json")
    _make_shop_db(str(tmp_path))

    reg1 = _file_registry(store_path)
    reg1.register_source(
        SQLiteDBSource(name="shop", properties={"connection": {"database_directory": str(tmp_path)}})
    )

    reg2 = _file_registry(store_path)
    assert reg2.get_source("shop") is None

    rebuilt = reg2.connect_source("shop")
    assert rebuilt is not None
    assert rebuilt.name == "shop"
    assert reg2.get_source("shop") is rebuilt

    assert reg2.connect_source("missing") is None
