"""Unit tests for DataRegistry.export_data."""
import csv
import json

import pandas as pd
import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.source import DataSource


# ---------- stub source ----------

ROWS = [
    {"id": 1, "name": "Alice", "city": "Prague"},
    {"id": 2, "name": "Bob",   "city": "Brno"},
    {"id": 3, "name": "Carol", "city": "Prague"},
]


class StubSource(DataSource):
    """DataSource that returns ROWS from execute_query, recording call args."""

    def __init__(self, rows=None):
        super().__init__("stub")
        self._rows = rows if rows is not None else list(ROWS)
        self.last_query = None
        self.last_collection = None

    def execute_query(self, query=None, database=None, collection=None, optional_properties=None):
        self.last_query = query
        self.last_collection = collection
        if isinstance(query, dict):
            return [r for r in self._rows if all(r.get(k) == v for k, v in query.items())]
        return list(self._rows)

    def fetch_databases(self):
        return ["default"]

    def fetch_database_collections(self, database):
        return ["items"]


@pytest.fixture
def reg(tmp_path):
    r = DataRegistry(store=MemoryJSONSource())
    src = StubSource()
    r.register_source(src)
    return r, src, tmp_path


# ---------- format inference from extension ----------

class TestFormatInference:
    def test_csv_extension(self, reg):
        r, _, tmp = reg
        out = tmp / "out.csv"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "csv"
        assert out.exists()

    def test_json_extension(self, reg):
        r, _, tmp = reg
        out = tmp / "out.json"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "json"
        assert out.exists()

    def test_jsonl_extension(self, reg):
        r, _, tmp = reg
        out = tmp / "out.jsonl"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "jsonl"
        assert out.exists()

    def test_parquet_extension(self, reg):
        pytest.importorskip("pyarrow")
        r, _, tmp = reg
        out = tmp / "out.parquet"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "parquet"
        assert out.exists()

    def test_unknown_extension_defaults_to_csv(self, reg):
        r, _, tmp = reg
        out = tmp / "out.dat"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "csv"

    def test_no_extension_defaults_to_csv(self, reg):
        r, _, tmp = reg
        out = tmp / "out"
        result = r.export_data("stub", str(out), collection="items")
        assert result["format"] == "csv"


# ---------- fmt override ----------

class TestFmtOverride:
    def test_fmt_overrides_extension(self, reg):
        r, _, tmp = reg
        out = tmp / "out.csv"
        result = r.export_data("stub", str(out), collection="items", fmt="json")
        assert result["format"] == "json"
        data = json.loads(out.read_text())
        assert isinstance(data, list)

    def test_unsupported_fmt_raises(self, reg):
        r, _, tmp = reg
        out = tmp / "out.xml"
        with pytest.raises(ValueError, match="Unsupported export format"):
            r.export_data("stub", str(out), collection="items", fmt="xml")


# ---------- file content ----------

class TestFileContent:
    def test_csv_has_all_rows(self, reg):
        r, _, tmp = reg
        out = tmp / "out.csv"
        r.export_data("stub", str(out), collection="items")
        with open(out) as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 3
        assert reader[0]["name"] == "Alice"
        assert reader[1]["name"] == "Bob"

    def test_csv_has_correct_columns(self, reg):
        r, _, tmp = reg
        out = tmp / "out.csv"
        r.export_data("stub", str(out), collection="items")
        with open(out) as f:
            header = f.readline().strip().split(",")
        assert set(header) == {"id", "name", "city"}

    def test_json_is_list_of_records(self, reg):
        r, _, tmp = reg
        out = tmp / "out.json"
        r.export_data("stub", str(out), collection="items")
        data = json.loads(out.read_text())
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["name"] == "Alice"

    def test_jsonl_each_line_is_valid_json(self, reg):
        r, _, tmp = reg
        out = tmp / "out.jsonl"
        r.export_data("stub", str(out), collection="items")
        lines = out.read_text().strip().splitlines()
        assert len(lines) == 3
        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["name"] == "Alice"

    def test_parquet_readable_as_dataframe(self, reg):
        pytest.importorskip("pyarrow")
        r, _, tmp = reg
        out = tmp / "out.parquet"
        r.export_data("stub", str(out), collection="items")
        df = pd.read_parquet(out)
        assert len(df) == 3
        assert list(df["name"]) == ["Alice", "Bob", "Carol"]


# ---------- return value ----------

class TestReturnValue:
    def test_returns_success_status(self, reg):
        r, _, tmp = reg
        result = r.export_data("stub", str(tmp / "out.csv"), collection="items")
        assert result["status"] == "success"

    def test_returns_correct_rows_written(self, reg):
        r, _, tmp = reg
        result = r.export_data("stub", str(tmp / "out.csv"), collection="items")
        assert result["rows_written"] == 3

    def test_returns_absolute_path(self, reg, tmp_path):
        r, _, tmp = reg
        out = tmp / "out.csv"
        result = r.export_data("stub", str(out), collection="items")
        assert result["path"] == str(out.resolve())

    def test_returns_format(self, reg):
        r, _, tmp = reg
        result = r.export_data("stub", str(tmp / "out.json"), collection="items")
        assert result["format"] == "json"


# ---------- query passthrough ----------

class TestQueryPassthrough:
    def test_none_query_returns_all_rows(self, reg):
        r, src, tmp = reg
        r.export_data("stub", str(tmp / "out.csv"), collection="items", query=None)
        assert src.last_query is None

    def test_dict_query_passed_to_source(self, reg):
        r, src, tmp = reg
        r.export_data("stub", str(tmp / "out.csv"), collection="items", query={"city": "Prague"})
        assert src.last_query == {"city": "Prague"}

    def test_dict_query_filters_output(self, reg):
        r, _, tmp = reg
        out = tmp / "out.csv"
        r.export_data("stub", str(out), collection="items", query={"city": "Prague"})
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert all(row["city"] == "Prague" for row in rows)

    def test_collection_passed_to_source(self, reg):
        r, src, tmp = reg
        r.export_data("stub", str(tmp / "out.csv"), collection="orders")
        assert src.last_collection == "orders"


# ---------- edge cases ----------

class TestEdgeCases:
    def test_empty_result_writes_header_only_csv(self, tmp_path):
        r = DataRegistry(store=MemoryJSONSource())
        src = StubSource(rows=[])
        r.register_source(src)
        out = tmp_path / "out.csv"
        result = r.export_data("stub", str(out), collection="items")
        assert result["rows_written"] == 0
        assert out.exists()

    def test_parent_directory_created(self, reg):
        r, _, tmp = reg
        out = tmp / "subdir" / "nested" / "out.csv"
        r.export_data("stub", str(out), collection="items")
        assert out.exists()

    def test_unregistered_source_raises(self, reg):
        r, _, tmp = reg
        with pytest.raises(ValueError, match="not registered"):
            r.export_data("ghost", str(tmp / "out.csv"), collection="items")
