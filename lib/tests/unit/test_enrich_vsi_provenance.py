"""Regression tests for issue #98.

The deterministic base layer (`enrich_source`) writes `value_semantics` on every
attribute, which used to (a) make the LLM VSI step skip every attribute under the
default `rebuild=False`, and (b) overwrite LLM results on the next `rebuild=False`
run. VSI is now gated by provenance: it runs unless an LLM-sourced value_semantics
(`source == "llm"`) already exists, and the base layer no longer clobbers one.

Uses a deterministic fake llm_fn — no network calls.
"""
import json
import re
import sqlite3

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


def _make_registry(tmp_path, calls):
    def fake_llm(prompt):
        # Return a VSI result WITHOUT a source field: the code must stamp provenance.
        if "Value Semantics Inference (VSI) for multiple attributes" in prompt:
            calls.append("vsi")
            names = re.findall(r'"name": "([^"]+)"', prompt)
            return json.dumps(
                {n: {"primary_type": "LLM_TYPE", "semantic_type": "LLM_TYPE"} for n in names}
            )
        calls.append("other")
        return "{}"

    con = sqlite3.connect(str(tmp_path / "shop.db"))
    con.execute("CREATE TABLE orders (id INTEGER, status TEXT)")
    con.execute("INSERT INTO orders VALUES (1, 'PAID')")
    con.commit()
    con.close()

    reg = DataRegistry(metadata_enricher=MetaData(llm_fn=fake_llm))
    reg.register_source(
        SQLiteDBSource(name="src", properties={"connection": {"database_directory": str(tmp_path)}})
    )
    reg.sync_source("src", recursive=True)
    reg.collect_source_stats("src", recursive=True)
    return reg


def _vs(reg):
    return reg.get_source_database_collection_entity_attribute_property(
        "src", "shop", "public", "orders", "status", "value_semantics"
    ) or {}


def test_vsi_runs_under_default_rebuild_false(tmp_path):
    calls = []
    reg = _make_registry(tmp_path, calls)

    reg.enrich_source_metadata("src", recursive=True)  # rebuild=False (default)

    assert "vsi" in calls
    vs = _vs(reg)
    assert vs.get("semantic_type") == "LLM_TYPE"
    assert vs.get("source") == "llm"  # stamped by the code, not the LLM


def test_llm_result_survives_a_later_rebuild_false(tmp_path):
    calls = []
    reg = _make_registry(tmp_path, calls)

    reg.enrich_source_metadata("src", recursive=True)                # 1: rebuild=False
    reg.enrich_source_metadata("src", recursive=True, rebuild=True)  # 2: rebuild=True
    reg.enrich_source_metadata("src", recursive=True)                # 3: rebuild=False

    vs = _vs(reg)
    assert vs.get("semantic_type") == "LLM_TYPE"
    assert vs.get("source") == "llm"


def test_vsi_not_recalled_once_llm_sourced(tmp_path):
    calls = []
    reg = _make_registry(tmp_path, calls)

    reg.enrich_source_metadata("src", recursive=True)
    vsi_after_first = calls.count("vsi")
    reg.enrich_source_metadata("src", recursive=True)  # rebuild=False again

    assert calls.count("vsi") == vsi_after_first  # idempotent: VSI not re-run


def test_enrich_source_does_not_clobber_llm_value_semantics(tmp_path):
    calls = []
    reg = _make_registry(tmp_path, calls)

    reg.enrich_source_metadata("src", recursive=True)
    assert _vs(reg).get("source") == "llm"

    # The standalone deterministic pass must preserve the richer LLM result.
    reg.enrich_source("src")
    assert _vs(reg).get("source") == "llm"
