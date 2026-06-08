import pytest
from registry.registry import Registry


@pytest.fixture
def registry():
    return Registry()


def test_register_and_get_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["name"] == "users"
    assert record["type"] == "entity"


def test_list_records_by_type(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.register_record(name="orders", type="entity", scope="/source/mydb")
    registry.register_record(name="mydb", type="database", scope="/source/mydb")
    entities = registry.list_records(record_type="entity")
    assert len(entities) == 2
    assert all(r["type"] == "entity" for r in entities)


def test_list_records_by_scope(registry):
    registry.register_record(name="users", type="entity", scope="/source/db1")
    registry.register_record(name="orders", type="entity", scope="/source/db2")
    results = registry.list_records(scope="/source/db1")
    assert len(results) == 1
    assert results[0]["name"] == "users"


def test_deregister_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.deregister_record("users", "entity", "/source/mydb")
    assert registry.get_record("users", "entity", "/source/mydb") is None


def test_set_and_get_record_property(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_property("users", "entity", "/source/mydb", "stats", {"row_count": 42})
    value = registry.get_record_property("users", "entity", "/source/mydb", "stats")
    assert value == {"row_count": 42}


def test_update_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", description="old")
    registry.update_record("users", "entity", "/source/mydb", description="new")
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["description"] == "new"


def test_set_and_get_description(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_description("users", "entity", "/source/mydb", "User table")
    desc = registry.get_record_description("users", "entity", "/source/mydb")
    assert desc == "User table"
