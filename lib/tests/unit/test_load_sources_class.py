"""#109 (XR-01, deferred item) — BLUE_DATA_SOURCES_CONFIG must accept a
{"type": "class", "_class": ..., "properties": ...} entry so any DataSource
subclass (incl. sibling sources) can be pre-loaded into a host registry, not
just the built-in sqlite/postgres/mysql/mongodb types."""
import json

from blue_data.config import load_sources
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource


def _load(tmp_path, monkeypatch, sources):
    cfg = tmp_path / "sources.json"
    cfg.write_text(json.dumps({"sources": sources}))
    monkeypatch.setenv("BLUE_DATA_SOURCES_CONFIG", str(cfg))
    monkeypatch.setenv("BLUE_DATA_SOURCES_SYNC", "false")
    reg = DataRegistry(store=MemoryJSONSource())
    load_sources(reg)
    return reg


def test_class_entry_registers_and_persists_class(tmp_path, monkeypatch):
    reg = _load(tmp_path, monkeypatch, [{
        "name": "shop", "type": "class",
        "_class": "blue_data.source.sql.sqlite.sqlite_sql_source.SQLiteDBSource",
        "properties": {"connection": {"database_directory": str(tmp_path / "sql")}},
    }])
    assert "shop" in reg.list_sources()
    rec = reg.get_source_record("shop")
    assert rec["properties"]["_class"].endswith("SQLiteDBSource")
    # rebuildable from the persisted record alone
    reg.sources.pop("shop")
    assert type(reg.connect_source("shop")).__name__ == "SQLiteDBSource"


def test_class_entry_without_class_path_is_skipped(tmp_path, monkeypatch):
    reg = _load(tmp_path, monkeypatch, [{"name": "bad", "type": "class", "properties": {}}])
    assert "bad" not in reg.list_sources()


def test_unknown_type_still_skipped(tmp_path, monkeypatch):
    reg = _load(tmp_path, monkeypatch, [{"name": "huh", "type": "frobnicate"}])
    assert reg.list_sources() == []
