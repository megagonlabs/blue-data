import pytest
from core.schema import DataSchema


def test_add_and_get_entity():
    schema = DataSchema()
    schema.add_entity("users")
    entities = schema.get_entities()
    assert "users" in entities


def test_add_entity_property():
    schema = DataSchema()
    schema.add_entity("users")
    schema.add_entity_property("users", "age", {"type": "INTEGER"})
    attrs = schema.get_entities()["users"]["contents"]["attributes"]
    assert "age" in attrs
    assert attrs["age"]["info"] == {"type": "INTEGER"}


def test_has_entity():
    schema = DataSchema()
    assert not schema.has_entity("orders")
    schema.add_entity("orders")
    assert schema.has_entity("orders")


def test_add_relation():
    schema = DataSchema()
    schema.add_entity("users")
    schema.add_entity("orders")
    key = schema.add_relation("users", "PLACED", "orders")
    assert schema.has_relation("users", "PLACED", "orders")
    assert key in schema.get_relations()


def test_add_relation_property():
    schema = DataSchema()
    schema.add_entity("users")
    schema.add_entity("orders")
    key = schema.add_relation("users", "PLACED", "orders")
    schema.add_relation_property(key, "since", "DATE")
    assert schema.get_relations()[key]["properties"]["since"] == "DATE"


def test_duplicate_entity_gets_unique_key():
    schema = DataSchema()
    schema.add_entity("users")
    schema.add_entity("users")
    entities = schema.get_entities()
    assert "users" in entities
    assert "users__1" in entities
