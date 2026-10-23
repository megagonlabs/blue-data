"""End-to-end regression test for issue #92.

deregister_source (and the other deregister_* helpers) must remove the source
record AND all its descendant database/collection/entity/attribute records, so
nothing from the removed source keeps showing up in listings or search.
"""
import os
import sqlite3
import tempfile

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def synced_registry():
    d = tempfile.mkdtemp()
    con = sqlite3.connect(os.path.join(d, "shop.db"))
    con.execute("CREATE TABLE orders (id INTEGER, total REAL)")
    con.commit()
    con.close()

    reg = DataRegistry()
    reg.register_source(
        SQLiteDBSource(name="src", properties={"connection": {"database_directory": d}})
    )
    reg.sync_source("src", recursive=True)
    return reg


def test_deregister_source_removes_all_descendants(synced_registry):
    reg = synced_registry
    assert len(reg.list_records()) > 1  # source + database/collection/entity/attributes

    reg.deregister_source("src")

    assert reg.list_records() == []
    assert reg.search_records("orders") == []
    assert reg.get_source_record("src") is None


def test_deregister_source_database_removes_its_subtree(synced_registry):
    reg = synced_registry

    reg.deregister_source_database("src", "shop")

    # The source record stays; the database and everything under it are gone.
    remaining = sorted(f"{r['type']}:{r['name']}" for r in reg.list_records())
    assert remaining == ["source:src"]
    assert reg.search_records("orders") == []
