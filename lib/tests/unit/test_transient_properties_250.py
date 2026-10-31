"""Regression tests for issue #250.

DataRegistry.register_source persisted every property of a source, so a per-process
value like a UserSource's ``console`` was stored and a server that rebuilt the source
from the stored record got ``console=True`` — then wrote clarification prompts into the
stdio MCP protocol stream or blocked an HTTP request on the server's own stdin.

A source now declares such keys in ``_transient_properties`` and register_source drops
them before storing, so a rebuilt source gets the class default. No live server needed.
"""
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.source import DataSource


class _TransientSource(DataSource):
    """Declares a per-process property that must not be persisted. Base _connect is a
    no-op, so this can be registered and rebuilt without a live server."""

    _transient_properties = frozenset({"console"})


class _PlainSource(DataSource):
    """No transient properties — every property is persisted."""


def _stored_props(reg, name):
    return reg.get_record(name, "source", "/").get("properties", {})


def test_transient_property_absent_from_stored_record():
    reg = DataRegistry()
    reg.register_source(_TransientSource("u", properties={
        "connection": {"path": "/tmp/u.json"},
        "console": True,
    }))

    stored = _stored_props(reg, "u")
    assert "console" not in stored
    # Non-transient config still persists, so the source stays reconstructible.
    assert stored["connection"]["path"] == "/tmp/u.json"
    # The live in-process object keeps its full properties.
    assert reg.get_source("u").properties["console"] is True


def test_rebuilt_source_gets_class_default_not_registered_value():
    from blue_data.source.json.memory_json_source import MemoryJSONSource

    store = MemoryJSONSource()
    DataRegistry(store=store).register_source(_TransientSource("u", properties={
        "connection": {"path": "/tmp/u.json"},
        "console": True,
    }))

    # A fresh registry (a separate server process) rebuilds from the stored record.
    rebuilt = DataRegistry(store=store).connect_source("u")
    assert "console" not in rebuilt.properties


def test_non_transient_property_is_still_persisted():
    reg = DataRegistry()
    reg.register_source(_PlainSource("p", properties={
        "connection": {"path": "/tmp/p.json"},
        "console": True,
    }))
    # A source that does not declare console as transient keeps it (opt-in behaviour).
    assert _stored_props(reg, "p").get("console") is True


def test_default_transient_set_is_empty():
    assert DataSource._transient_properties == frozenset()
