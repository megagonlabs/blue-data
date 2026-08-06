"""Unit tests for JSONSource.execute_query on MemoryJSONSource and FileJSONSource."""
import pytest

from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.json.file_json_source import FileJSONSource


# ---------------------------------------------------------------------------
# shared fixture helpers
# ---------------------------------------------------------------------------

def _sources(tmp_path):
    return [
        MemoryJSONSource(),
        FileJSONSource(properties={"connection": {"path": str(tmp_path / "store.json")}}),
    ]


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_root_empty(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query({"op": "GET", "path": None})
            assert result == {}

    def test_get_root_dollar(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query({"op": "GET", "path": "$"})
            assert result == {}

    def test_get_existing_key(self, tmp_path):
        for src in _sources(tmp_path):
            src.set("users/alice", {"role": "admin"})
            result = src.execute_query({"op": "GET", "path": "users/alice"})
            assert result == {"role": "admin"}

    def test_get_missing_key_returns_none(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query({"op": "GET", "path": "no/such/key"})
            assert result is None

    def test_json_get_alias(self, tmp_path):
        for src in _sources(tmp_path):
            src.set("k", 42)
            assert src.execute_query({"op": "JSON.GET", "path": "k"}) == 42


# ---------------------------------------------------------------------------
# SET
# ---------------------------------------------------------------------------

class TestSet:
    def test_set_and_read_back(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "SET", "path": "cfg/debug", "value": True})
            assert src.get("cfg/debug") is True

    def test_set_returns_none(self, tmp_path):
        for src in _sources(tmp_path):
            result = src.execute_query({"op": "SET", "path": "x", "value": 1})
            assert result is None

    def test_json_set_alias(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "JSON.SET", "path": "flag", "value": False})
            assert src.get("flag") is False

    def test_set_overwrites(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "SET", "path": "v", "value": "first"})
            src.execute_query({"op": "SET", "path": "v", "value": "second"})
            assert src.get("v") == "second"


# ---------------------------------------------------------------------------
# DEL
# ---------------------------------------------------------------------------

class TestDel:
    def test_del_removes_key(self, tmp_path):
        for src in _sources(tmp_path):
            src.set("temp", 99)
            src.execute_query({"op": "DEL", "path": "temp"})
            assert src.get("temp") is None

    def test_del_returns_none(self, tmp_path):
        for src in _sources(tmp_path):
            src.set("x", 1)
            result = src.execute_query({"op": "DEL", "path": "x"})
            assert result is None

    def test_json_del_alias(self, tmp_path):
        for src in _sources(tmp_path):
            src.set("remove_me", "bye")
            src.execute_query({"op": "JSON.DEL", "path": "remove_me"})
            assert src.get("remove_me") is None

    def test_del_missing_key_no_error(self, tmp_path):
        for src in _sources(tmp_path):
            src.execute_query({"op": "DEL", "path": "ghost"})  # should not raise


# ---------------------------------------------------------------------------
# error cases
# ---------------------------------------------------------------------------

class TestErrors:
    def test_non_dict_query_raises(self, tmp_path):
        src = MemoryJSONSource()
        with pytest.raises(ValueError, match="expects query as a dict"):
            src.execute_query("GET /foo")

    def test_unknown_op_raises(self, tmp_path):
        src = MemoryJSONSource()
        with pytest.raises(ValueError, match="Unsupported"):
            src.execute_query({"op": "SCAN", "path": "foo"})
