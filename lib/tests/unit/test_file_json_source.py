"""Unit tests for FileJSONSource."""
import json
import pytest
from source.json.file_json_source import FileJSONSource


@pytest.fixture
def src(tmp_path):
    return FileJSONSource(str(tmp_path / "store.json"))


def test_initial_file_created(tmp_path):
    path = str(tmp_path / "new.json")
    FileJSONSource(path)
    assert (tmp_path / "new.json").exists()


def test_get_root_empty(src):
    assert src.get(None) == {}
    assert src.get("$") == {}
    assert src.get("") == {}


def test_set_and_get(src):
    src.set("users/alice", {"role": "admin"})
    assert src.get("users/alice") == {"role": "admin"}


def test_set_root(src):
    src.set("$", {"version": 2})
    assert src.get("$")["version"] == 2


def test_set_overwrites_existing(src):
    src.set("k", "v1")
    src.set("k", "v2")
    assert src.get("k") == "v2"


def test_get_missing_key_returns_none(src):
    assert src.get("no/such/key") is None


def test_delete_key(src):
    src.set("temp", 42)
    src.delete("temp")
    assert src.get("temp") is None


def test_delete_root_clears(src):
    src.set("a", 1)
    src.set("b", 2)
    src.delete("$")
    assert src.get(None) == {}


def test_delete_missing_no_error(src):
    src.delete("ghost")   # should not raise


def test_data_written_to_file(tmp_path):
    path = str(tmp_path / "store.json")
    src = FileJSONSource(path)
    src.set("key", "value")
    with open(path) as f:
        raw = json.load(f)
    assert raw["key"] == "value"


def test_data_persists_across_instances(tmp_path):
    path = str(tmp_path / "store.json")
    src1 = FileJSONSource(path)
    src1.set("persistent", True)
    src2 = FileJSONSource(path)
    assert src2.get("persistent") is True


def test_multiple_keys(src):
    for i in range(5):
        src.set(f"key_{i}", i)
    for i in range(5):
        assert src.get(f"key_{i}") == i
