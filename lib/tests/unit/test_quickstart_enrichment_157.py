"""Regression test for issue #157 (quickstart enrichment).

The quickstart's deterministic step showed `registry.enrich_source("mydb")`, which only
sets semantic column types — it does NOT produce the advertised event-table / event-time
/ value-axis / semantic-role annotations. Those come from the metadata pipeline
(`enrich_source_metadata`), which runs deterministically with `MetaData(llm_fn=None)`.

This test pins that difference so the documented snippet stays correct. No API key.
"""
import json
import os
import sqlite3
import tempfile

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


@pytest.fixture
def source():
    d = tempfile.mkdtemp()
    con = sqlite3.connect(os.path.join(d, "mydb.db"))
    con.executescript(
        "CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER, "
        "order_date TEXT, amount REAL, status TEXT);"
        "INSERT INTO orders VALUES (1,10,'2021-01-05',149.0,'shipped'),"
        "(2,11,'2021-02-09',49.5,'pending'),(3,10,'2021-03-01',999.0,'shipped'),"
        "(4,12,'2021-03-15',10.0,'cancelled'),(5,11,'2021-04-02',250.0,'shipped');"
    )
    con.commit()
    con.close()
    return SQLiteDBSource(name="mydb", properties={"connection": {"database_directory": d}})


def _annotation_blob(registry):
    """Concatenated JSON of every entity/attribute record's properties."""
    return json.dumps([
        r.get("properties", {})
        for r in registry.list_records()
        if r.get("type") in ("entity", "attribute")
    ])


def test_deterministic_metadata_pipeline_produces_annotations(source):
    # The documented deterministic snippet (llm_fn=None, no API key).
    registry = DataRegistry(metadata_enricher=MetaData(llm_fn=None))
    registry.register_source(source)
    registry.sync_source("mydb", recursive=True)
    registry.collect_source_stats("mydb", recursive=True)
    registry.enrich_source_metadata("mydb", recursive=True)

    blob = _annotation_blob(registry)
    assert "semantic_role" in blob          # roles on attributes
    assert "EVENT_TIME" in blob             # order_date detected as an event-time column


def test_plain_enrich_source_lacks_pipeline_annotations(source):
    # The old snippet: enrich_source alone sets only semantic column types.
    registry = DataRegistry()
    registry.register_source(source)
    registry.sync_source("mydb", recursive=True)
    registry.collect_source_stats("mydb", recursive=True)
    registry.enrich_source("mydb")

    blob = _annotation_blob(registry)
    assert "semantic_role" not in blob
    assert "EVENT_TIME" not in blob
