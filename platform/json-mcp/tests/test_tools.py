import os
import pytest

import json_mcp.config as config_module
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.json.file_json_source import FileJSONSource
from json_mcp.server import json_get, json_set, json_delete, json_list_keys, json_get_all


@pytest.fixture(autouse=True)
def fresh_store():
    store = MemoryJSONSource()
    config_module._store = store
    yield store
    config_module._store = None


@pytest.fixture
def file_store(tmp_path):
    path = str(tmp_path / "store.json")
    store = FileJSONSource(properties={"connection": {"path": path}})
    config_module._store = store
    yield store
    config_module._store = None


# ---------------------------------------------------------------------------
# json_set / json_get
# ---------------------------------------------------------------------------

def test_set_and_get():
    json_set("users/alice", {"name": "Alice", "age": 30})
    result = json_get("users/alice")
    assert result["value"] == {"name": "Alice", "age": 30}
    assert result["path"] == "users/alice"


def test_get_missing_key_returns_none():
    result = json_get("does/not/exist")
    assert result["value"] is None


def test_set_string_value():
    json_set("config/env", "production")
    assert json_get("config/env")["value"] == "production"


def test_set_numeric_value():
    json_set("stats/count", 42)
    assert json_get("stats/count")["value"] == 42


def test_set_root():
    json_set("$", {"version": 1})
    result = json_get("$")
    assert result["value"]["version"] == 1


def test_set_returns_ok():
    r = json_set("key", "val")
    assert r["status"] == "ok"
    assert r["path"] == "key"


def test_overwrite_existing_key():
    json_set("x", 1)
    json_set("x", 2)
    assert json_get("x")["value"] == 2


# ---------------------------------------------------------------------------
# json_delete
# ---------------------------------------------------------------------------

def test_delete_existing_key():
    json_set("temp", "data")
    json_delete("temp")
    assert json_get("temp")["value"] is None


def test_delete_missing_key_no_error():
    r = json_delete("ghost")
    assert r["status"] == "ok"


def test_delete_returns_path():
    r = json_delete("some/path")
    assert r["path"] == "some/path"


def test_delete_root_clears_store():
    json_set("a", 1)
    json_set("b", 2)
    json_delete("$")
    assert json_get_all()["value"] == {}


# ---------------------------------------------------------------------------
# json_list_keys
# ---------------------------------------------------------------------------

def test_list_keys_empty():
    result = json_list_keys()
    assert result["keys"] == []


def test_list_keys_returns_all():
    json_set("alpha", 1)
    json_set("beta", 2)
    json_set("gamma", 3)
    keys = json_list_keys()["keys"]
    assert set(keys) == {"alpha", "beta", "gamma"}


def test_list_keys_prefix_filter():
    json_set("source/sqlite/db1", 1)
    json_set("source/sqlite/db2", 2)
    json_set("source/postgres/db1", 3)
    json_set("other/key", 4)
    keys = json_list_keys(prefix="source/sqlite")["keys"]
    assert set(keys) == {"source/sqlite/db1", "source/sqlite/db2"}


def test_list_keys_sorted():
    json_set("c", 3)
    json_set("a", 1)
    json_set("b", 2)
    keys = json_list_keys()["keys"]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# json_get_all
# ---------------------------------------------------------------------------

def test_get_all_empty():
    result = json_get_all()
    assert result["value"] == {}


def test_get_all_returns_full_store():
    json_set("x", 10)
    json_set("y", 20)
    data = json_get_all()["value"]
    assert data["x"] == 10
    assert data["y"] == 20


# ---------------------------------------------------------------------------
# FileJSONSource backend
# ---------------------------------------------------------------------------

def test_file_set_and_get(file_store):
    json_set("name", "blue-data")
    assert json_get("name")["value"] == "blue-data"


def test_file_persists_across_reads(file_store, tmp_path):
    json_set("persistent", True)
    # Re-read directly from the file to confirm it was written
    path = str(tmp_path / "store.json")
    import json
    with open(path) as f:
        raw = json.load(f)
    assert raw["persistent"] is True


def test_file_delete(file_store):
    json_set("tmp", 99)
    json_delete("tmp")
    assert json_get("tmp")["value"] is None


def test_file_list_keys(file_store):
    json_set("a/1", "x")
    json_set("a/2", "y")
    json_set("b/1", "z")
    keys = json_list_keys(prefix="a/")["keys"]
    assert set(keys) == {"a/1", "a/2"}


def test_get_store_memory(monkeypatch):
    config_module._store = None
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "memory")
    store = config_module.get_store()
    assert isinstance(store, MemoryJSONSource)
    config_module._store = None


def test_get_store_file(monkeypatch, tmp_path):
    config_module._store = None
    path = str(tmp_path / "test.json")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_FILE", path)
    store = config_module.get_store()
    assert isinstance(store, FileJSONSource)
    config_module._store = None
