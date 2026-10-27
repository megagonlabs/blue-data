"""Regression tests for issue #106.

Sources connect eagerly at construction, and load_sources had no per-source error
handling, so one unreachable configured source made get_registry() raise and every
platform tool fail. load_sources now isolates per-source failures: it logs them,
registers the source as unavailable, and continues loading the healthy ones.
"""
import json
import sqlite3

from blue_data.config import load_sources
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.source import DataSource


class _BoomSource(DataSource):
    """Fails at construction, like a source whose eager connect is refused."""

    def __init__(self, name, properties=None):
        raise RuntimeError("cannot connect")


_BOOM_PATH = f"{_BoomSource.__module__}.{_BoomSource.__qualname__}"


def _write_config(tmp_path):
    sqlite3.connect(str(tmp_path / "shop.db")).execute("CREATE TABLE orders(id INTEGER)")
    config = {
        "sources": [
            {"type": "sqlite", "name": "shop",
             "properties": {"connection": {"database_directory": str(tmp_path)}}},
            {"type": "class", "name": "down", "_class": _BOOM_PATH,
             "properties": {"connection": {"password": "PLACEHOLDER-SECRET"}}},
        ]
    }
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(config))
    return str(path)


def test_unreachable_source_does_not_abort_load(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_SOURCES_CONFIG", _write_config(tmp_path))
    monkeypatch.setenv("BLUE_DATA_SOURCES_SYNC", "false")

    reg = DataRegistry()
    load_sources(reg)  # must not raise despite 'down' failing to construct

    assert "shop" in reg.list_sources()
    assert reg.get_source("shop") is not None  # healthy source is live


def test_failed_source_registered_unavailable_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_SOURCES_CONFIG", _write_config(tmp_path))
    monkeypatch.setenv("BLUE_DATA_SOURCES_SYNC", "false")

    reg = DataRegistry()
    load_sources(reg)

    assert "down" in reg.list_sources()       # reported, not dropped
    assert reg.get_source("down") is None      # no live object
    record = reg.get_source_record("down")
    assert record["properties"]["status"] == "unavailable"
    assert "PLACEHOLDER-SECRET" not in json.dumps(record)  # credentials stripped
