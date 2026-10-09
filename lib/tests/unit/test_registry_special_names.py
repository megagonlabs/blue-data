"""Regression tests for #91 — record names containing characters the JSON
stores treat as structural ("." as a sub-path separator, "*"/"?" as Redis SCAN
globs) must still round-trip as flat records and not corrupt siblings.

Covered here on the memory and file backends; Redis is covered in
tests/integration/test_redis_registry.py (needs a running server)."""
import os
import tempfile

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.registry import Registry
from blue_data.source.json.file_json_source import FileJSONSource
from blue_data.source.json.memory_json_source import MemoryJSONSource


def _memory_store():
    return MemoryJSONSource()


def _file_store():
    path = os.path.join(tempfile.mkdtemp(), "store.json")
    return FileJSONSource(properties={"connection": {"path": path}})


STORE_FACTORIES = {"memory": _memory_store, "file": _file_store}


@pytest.fixture(params=STORE_FACTORIES.keys())
def store(request):
    return STORE_FACTORIES[request.param]()


def test_dotted_database_does_not_vanish_or_corrupt_sibling(store):
    """Exact reproduction from issue #91 (bd03.py)."""
    reg = DataRegistry(store=store)
    reg.register_source_database("src", "sales")
    reg.register_source_database("src", "sales.v2")  # e.g. SQLite file sales.v2.db
    reg.register_source_database_collection_entity_attribute(
        "src", "sales", "public", "orders", "price.usd"
    )

    databases = sorted(r["name"] for r in reg.list_source_databases("src"))
    assert databases == ["sales", "sales.v2"]

    # The sibling "sales" record must not have gained a "v2" sub-key.
    sales = reg.get_source_database("src", "sales")
    assert "v2" not in sales
    assert set(sales.keys()) == {
        "contents", "created_by", "description", "icon",
        "name", "properties", "scope", "type",
    }

    attrs = [r["name"] for r in reg.list_entity_attributes("src", "sales", "public", "orders")]
    assert attrs == ["price.usd"]


@pytest.mark.parametrize("name", ["sales.v2", "a/b", "$special", "with space", "a.b.c"])
def test_special_char_names_round_trip(store, name):
    reg = Registry(store=store)
    reg.register_record(name=name, type="entity", scope="/source/mydb")

    record = reg.get_record(name, "entity", "/source/mydb")
    assert record is not None
    assert record["name"] == name

    listed = [r["name"] for r in reg.list_records(record_type="entity", scope="/source/mydb")]
    assert listed == [name]


def test_dotted_and_plain_siblings_are_independent(store):
    reg = Registry(store=store)
    reg.register_record(name="sales", type="database", scope="/source/src")
    reg.register_record(name="sales.v2", type="database", scope="/source/src")

    reg.set_record_property("sales", "database", "/source/src", "stats", {"rows": 1})
    reg.set_record_property("sales.v2", "database", "/source/src", "stats", {"rows": 2})

    assert reg.get_record_property("sales", "database", "/source/src", "stats") == {"rows": 1}
    assert reg.get_record_property("sales.v2", "database", "/source/src", "stats") == {"rows": 2}

    # Deleting the dotted record must leave the plain sibling intact.
    reg.deregister_record("sales.v2", "database", "/source/src")
    assert reg.get_record("sales.v2", "database", "/source/src") is None
    assert reg.get_record("sales", "database", "/source/src") is not None
    assert reg.get_record_property("sales", "database", "/source/src", "stats") == {"rows": 1}
