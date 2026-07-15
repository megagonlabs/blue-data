import json
import os

import pandas as pd
import pytest

from blue_data.source.file.file_source import FileSource


@pytest.fixture
def src(tmp_path):
    return FileSource("test", directory=str(tmp_path))


def _write_csv(tmp_path, name, rows):
    path = tmp_path / f"{name}.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_json(tmp_path, name, rows):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(rows))
    return path


def _write_jsonl(tmp_path, name, rows):
    path = tmp_path / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    return path


# ---------- fetch_databases ----------

def test_fetch_databases(src):
    assert src.fetch_databases() == ["default"]


# ---------- fetch_database_collections ----------

def test_collections_empty(src, tmp_path):
    assert src.fetch_database_collections("default") == []


def test_collections_csv(src, tmp_path):
    _write_csv(tmp_path, "orders", [{"id": 1}])
    assert src.fetch_database_collections("default") == ["orders"]


def test_collections_multiple_formats(src, tmp_path):
    _write_csv(tmp_path, "orders", [{"id": 1}])
    _write_json(tmp_path, "users", [{"id": 2}])
    _write_jsonl(tmp_path, "events", [{"id": 3}])
    assert src.fetch_database_collections("default") == ["events", "orders", "users"]


def test_collections_ignores_unknown_extensions(src, tmp_path):
    (tmp_path / "readme.txt").write_text("ignore me")
    assert src.fetch_database_collections("default") == []


# ---------- fetch_database_collection_metadata ----------

def test_metadata_returns_format_and_size(src, tmp_path):
    _write_csv(tmp_path, "orders", [{"id": 1}])
    meta = src.fetch_database_collection_metadata("default", "orders")
    assert meta["format"] == "csv"
    assert meta["size_bytes"] > 0


def test_metadata_missing_collection(src):
    assert src.fetch_database_collection_metadata("default", "nonexistent") == {}


# ---------- fetch_database_collection_entities ----------

def test_entities_infers_schema_from_csv(src, tmp_path):
    _write_csv(tmp_path, "orders", [{"id": 1, "amount": 9.99, "label": "x"}])
    entities = src.fetch_database_collection_entities("default", "orders")
    assert "orders" in entities
    attrs = entities["orders"]["contents"]["attributes"]
    assert "id" in attrs
    assert "amount" in attrs
    assert "label" in attrs


def test_entities_empty_file(src, tmp_path):
    _write_csv(tmp_path, "empty", [])
    assert src.fetch_database_collection_entities("default", "empty") == {}


def test_entities_missing_collection(src):
    assert src.fetch_database_collection_entities("default", "ghost") == {}


def test_entities_type_inference(src, tmp_path):
    _write_csv(tmp_path, "data", [{"count": 1, "score": 1.5, "name": "a"}])
    entities = src.fetch_database_collection_entities("default", "data")
    attrs = entities["data"]["contents"]["attributes"]
    assert attrs["count"]["info"] == "int"
    assert attrs["score"]["info"] == "float"
    assert attrs["name"]["info"] == "str"


# ---------- execute_query ----------

def test_execute_query_returns_all_rows(src, tmp_path):
    rows = [{"id": 1, "city": "NYC"}, {"id": 2, "city": "LA"}]
    _write_csv(tmp_path, "orders", rows)
    result = src.execute_query(None, collection="orders")
    assert len(result) == 2


def test_execute_query_filters_by_dict(src, tmp_path):
    rows = [{"id": 1, "city": "NYC"}, {"id": 2, "city": "LA"}]
    _write_csv(tmp_path, "orders", rows)
    result = src.execute_query({"city": "NYC"}, collection="orders")
    assert len(result) == 1
    assert result[0]["city"] == "NYC"


def test_execute_query_no_collection_raises(src):
    with pytest.raises(ValueError):
        src.execute_query(None)


def test_execute_query_missing_collection_returns_empty(src):
    assert src.execute_query(None, collection="nonexistent") == []


def test_execute_query_json(src, tmp_path):
    rows = [{"x": 1}, {"x": 2}]
    _write_json(tmp_path, "items", rows)
    result = src.execute_query(None, collection="items")
    assert result == rows


def test_execute_query_jsonl(src, tmp_path):
    rows = [{"x": 1}, {"x": 2}]
    _write_jsonl(tmp_path, "events", rows)
    result = src.execute_query(None, collection="events")
    assert result == rows


# ---------- fetch_entity_stats ----------

def test_entity_stats_row_count(src, tmp_path):
    rows = [{"id": i} for i in range(5)]
    _write_csv(tmp_path, "data", rows)
    stats = src.fetch_entity_stats("default", "data", "data")
    assert stats["row_count"] == 5
    assert stats["row_sample_size"] == 5
    assert stats["row_samples_aligned"] is True


def test_entity_stats_missing_collection(src):
    stats = src.fetch_entity_stats("default", "ghost", "ghost")
    assert stats["row_count"] == 0
    assert stats["row_samples_aligned"] is False


# ---------- fetch_source_stats ----------

def test_source_stats(src, tmp_path):
    _write_csv(tmp_path, "a", [{"x": 1}])
    _write_csv(tmp_path, "b", [{"x": 2}])
    stats = src.fetch_source_stats()
    assert stats["total_collections"] == 2
    assert stats["total_bytes"] > 0


# ---------- import_data ----------

def _source_with_rows(tmp_path, name, rows):
    """Helper: a FileSource whose *name* collection already has *rows*."""
    src = FileSource(f"src_{name}", directory=str(tmp_path / f"src_{name}"))
    _write_csv(tmp_path / f"src_{name}", name, rows)
    return src


def test_import_creates_csv_by_default(src, tmp_path):
    (tmp_path / "src_orders").mkdir()
    source = _source_with_rows(tmp_path, "orders", [{"id": 1, "val": "a"}])
    result = src.import_data(source, "orders")
    assert result["status"] == "success"
    assert result["format"] == "csv"
    assert result["rows_written"] == 1
    assert os.path.exists(tmp_path / "orders.csv")


def test_import_creates_json(src, tmp_path):
    (tmp_path / "src_items").mkdir()
    source = _source_with_rows(tmp_path, "items", [{"id": 1}])
    src.import_data(source, "items", options={"format": "json"})
    assert os.path.exists(tmp_path / "items.json")


def test_import_creates_jsonl(src, tmp_path):
    (tmp_path / "src_events").mkdir()
    source = _source_with_rows(tmp_path, "events", [{"id": 1}])
    src.import_data(source, "events", options={"format": "jsonl"})
    assert os.path.exists(tmp_path / "events.jsonl")


def test_import_append_adds_rows(src, tmp_path):
    (tmp_path / "src_orders").mkdir()
    source = _source_with_rows(tmp_path, "orders", [{"id": 1}])
    src.import_data(source, "orders")
    source2 = _source_with_rows(tmp_path, "orders", [{"id": 2}])
    src.import_data(source2, "orders", mode="append")
    rows = src.execute_query(None, collection="orders")
    assert len(rows) == 2


def test_import_overwrite_replaces_rows(src, tmp_path):
    (tmp_path / "src_orders").mkdir()
    source = _source_with_rows(tmp_path, "orders", [{"id": 1}, {"id": 2}])
    src.import_data(source, "orders")
    source2 = _source_with_rows(tmp_path, "orders", [{"id": 99}])
    src.import_data(source2, "orders", mode="overwrite")
    rows = src.execute_query(None, collection="orders")
    assert len(rows) == 1
    assert rows[0]["id"] == 99


def test_import_infers_format_from_existing_file(src, tmp_path):
    _write_json(tmp_path, "data", [{"x": 1}])
    (tmp_path / "src_data").mkdir()
    source = _source_with_rows(tmp_path, "data", [{"x": 2}])
    src.import_data(source, "data", mode="append")
    rows = src.execute_query(None, collection="data")
    assert len(rows) == 2
    assert (tmp_path / "data.json").exists()


def test_execute_query_parquet(src, tmp_path):
    rows = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
    pd.DataFrame(rows).to_parquet(tmp_path / "items.parquet", index=False)
    result = src.execute_query(None, collection="items")
    assert len(result) == 2


def test_import_creates_parquet(src, tmp_path):
    (tmp_path / "src_data").mkdir()
    source = _source_with_rows(tmp_path, "data", [{"id": 1}])
    src.import_data(source, "data", options={"format": "parquet"})
    assert os.path.exists(tmp_path / "data.parquet")
    rows = src.execute_query(None, collection="data")
    assert len(rows) == 1


def test_import_empty_source(src, tmp_path):
    (tmp_path / "src_empty").mkdir()
    source = FileSource("empty_src", directory=str(tmp_path / "src_empty"))
    _write_csv(tmp_path / "src_empty", "empty", [])
    result = src.import_data(source, "empty")
    assert result["status"] == "success"
    assert result["rows_written"] == 0
    assert os.path.exists(tmp_path / "empty.csv")


# ---------- cross-format import ----------

def test_import_csv_source_to_json_target(src, tmp_path):
    (tmp_path / "src_orders").mkdir()
    source = _source_with_rows(tmp_path, "orders", [{"id": 1, "city": "NYC"}])
    src.import_data(source, "orders", options={"format": "json"})
    assert (tmp_path / "orders.json").exists()
    rows = src.execute_query(None, collection="orders")
    assert len(rows) == 1
    assert rows[0]["city"] == "NYC"


def test_import_csv_source_to_parquet_target(src, tmp_path):
    (tmp_path / "src_orders").mkdir()
    source = _source_with_rows(tmp_path, "orders", [{"id": 1, "amount": 99.5}])
    src.import_data(source, "orders", options={"format": "parquet"})
    assert (tmp_path / "orders.parquet").exists()
    rows = src.execute_query(None, collection="orders")
    assert rows[0]["amount"] == 99.5


def test_import_parquet_source_to_csv_target(src, tmp_path):
    src_dir = tmp_path / "parquet_src"
    src_dir.mkdir()
    pd.DataFrame([{"x": 10}, {"x": 20}]).to_parquet(src_dir / "data.parquet", index=False)
    source = FileSource("parquet_src", directory=str(src_dir))
    src.import_data(source, "data", options={"format": "csv"})
    assert (tmp_path / "data.csv").exists()
    rows = src.execute_query(None, collection="data")
    assert len(rows) == 2


# ---------- parquet append ----------

def test_import_parquet_append(src, tmp_path):
    (tmp_path / "src_a").mkdir()
    source_a = _source_with_rows(tmp_path, "a", [{"id": 1}])
    src.import_data(source_a, "a", options={"format": "parquet"})
    (tmp_path / "src_a2").mkdir()
    source_b = FileSource("src_a2", directory=str(tmp_path / "src_a2"))
    _write_csv(tmp_path / "src_a2", "a", [{"id": 2}])
    src.import_data(source_b, "a", mode="append")
    rows = src.execute_query(None, collection="a")
    assert len(rows) == 2


# ---------- missing source collection ----------

def test_import_source_collection_missing_writes_empty(src, tmp_path):
    source = FileSource("empty_src", directory=str(tmp_path / "empty_src"))
    result = src.import_data(source, "ghost")
    assert result["status"] == "success"
    assert result["rows_written"] == 0


# ---------- end-to-end scenario ----------

def test_e2e_full_collection_copy(tmp_path):
    """Copy a collection from one FileSource directory to another and verify round-trip."""
    src_dir = tmp_path / "source_store"
    dst_dir = tmp_path / "dest_store"
    src_dir.mkdir()
    dst_dir.mkdir()

    rows = [{"id": i, "name": f"item_{i}", "price": i * 1.5} for i in range(5)]
    pd.DataFrame(rows).to_csv(src_dir / "products.csv", index=False)

    source = FileSource("source", directory=str(src_dir))
    dest = FileSource("dest", directory=str(dst_dir))

    result = dest.import_data(source, "products")
    assert result["status"] == "success"
    assert result["rows_written"] == 5

    copied = dest.execute_query(None, collection="products")
    assert len(copied) == 5
    assert copied[0]["name"] == "item_0"
    assert copied[4]["price"] == 6.0


def test_e2e_append_then_overwrite(tmp_path):
    """Append two batches then overwrite — final state should only have overwrite batch."""
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    source = FileSource("src", directory=str(src_dir))
    dest = FileSource("dst", directory=str(dst_dir))

    pd.DataFrame([{"id": 1}]).to_csv(src_dir / "orders.csv", index=False)
    dest.import_data(source, "orders")

    pd.DataFrame([{"id": 2}]).to_csv(src_dir / "orders.csv", index=False)
    dest.import_data(source, "orders", mode="append")

    rows = dest.execute_query(None, collection="orders")
    assert len(rows) == 2

    pd.DataFrame([{"id": 99}]).to_csv(src_dir / "orders.csv", index=False)
    dest.import_data(source, "orders", mode="overwrite")

    rows = dest.execute_query(None, collection="orders")
    assert len(rows) == 1
    assert rows[0]["id"] == 99


def test_import_data_stub_on_base():
    from blue_data.source.source import DataSource
    ds = DataSource("base")
    source = DataSource("source")
    result = ds.import_data(source, "col")
    assert result == {}
