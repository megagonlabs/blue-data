"""Regression tests for issue #184.

DataRegistry.create_source_* passes ``overwrite=`` to the source's create_*
methods. The base DataSource implementations must declare that keyword, otherwise
any source that inherits them (e.g. MemoryJSONSource) raises TypeError when created
through the registry.
"""
import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource


def test_base_create_methods_accept_overwrite_keyword():
    """The reproduction from the issue: base create_* accept overwrite=."""
    s = MemoryJSONSource("m", {"connection": {"protocol": "json/memory"}})

    assert s.create_database("db1", properties={}, overwrite=False) == {}
    assert s.create_database_collection("db1", "c1", properties={}, overwrite=False) == {}
    assert s.create_database_collection_entity(
        "db1", "c1", "e1", properties={}, overwrite=False
    ) == {}
    assert s.create_database_collection_relation(
        "db1", "c1", "r1", properties={}, overwrite=False
    ) == {}


@pytest.fixture
def registry():
    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(MemoryJSONSource("m", {"connection": {"protocol": "json/memory"}}))
    return reg


def test_create_source_database_through_registry(registry):
    # Must not raise TypeError: overwrite= reaches the inherited base create_database.
    registry.create_source_database("m", "db1")


def test_create_source_database_collection_through_registry(registry):
    registry.create_source_database_collection("m", "db1", "c1")


def test_create_source_database_collection_entity_through_registry(registry):
    registry.create_source_database_collection_entity("m", "db1", "c1", "e1")


def test_create_source_database_collection_relation_through_registry(registry):
    registry.create_source_database_collection_relation("m", "db1", "c1", "r1")
