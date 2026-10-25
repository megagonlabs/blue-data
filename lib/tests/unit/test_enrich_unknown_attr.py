"""Regression tests for issue #99.

LLM output is untrusted. A description keyed by an attribute that isn't in the
registry used to raise ValueError from set_record_description and abort
enrich_source_metadata for the whole source. Now the unknown key is skipped
(and logged), and a per-entity failure is isolated so the rest of the source
still gets enriched.

Uses a deterministic fake llm_fn — no network calls.
"""
import json
import re
import sqlite3

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


def _fake_llm(prompt):
    if "table_description" in prompt:
        attrs = re.findall(r"^- (\S+) \(", prompt, flags=re.M)
        out = {
            "table_description": "LLM table description",
            "attributes": {a: f"LLM desc of {a}" for a in attrs},
        }
        out["attributes"]["customer_name"] = "an attribute the model invented"
        return json.dumps(out)
    return "{}"


def _make_registry(tmp_path, enricher):
    con = sqlite3.connect(str(tmp_path / "shop.db"))
    con.execute("CREATE TABLE a_orders (id INTEGER)")
    con.execute("CREATE TABLE b_customers (id INTEGER)")
    con.execute("INSERT INTO a_orders VALUES (1)")
    con.execute("INSERT INTO b_customers VALUES (1)")
    con.commit()
    con.close()

    reg = DataRegistry(metadata_enricher=enricher)
    reg.register_source(
        SQLiteDBSource(name="src", properties={"connection": {"database_directory": str(tmp_path)}})
    )
    reg.sync_source("src", recursive=True)
    reg.collect_source_stats("src", recursive=True)
    return reg


def _entity_desc(reg, entity):
    return reg.get_source_database_collection_entity_description("src", "shop", "public", entity)


def test_unknown_attribute_in_llm_output_is_skipped(tmp_path):
    reg = _make_registry(tmp_path, MetaData(llm_fn=_fake_llm))

    reg.enrich_source_metadata("src", recursive=True)  # must not raise

    # Every table is enriched despite the hallucinated attribute key.
    assert _entity_desc(reg, "a_orders") == "LLM table description"
    assert _entity_desc(reg, "b_customers") == "LLM table description"
    # The real attribute got its description; the invented one was skipped.
    assert reg.get_source_database_collection_entity_attribute_description(
        "src", "shop", "public", "a_orders", "id"
    ) == "LLM desc of id"
    assert reg.get_source_database_collection_entity_attribute_description(
        "src", "shop", "public", "a_orders", "customer_name"
    ) is None


def test_per_entity_failure_does_not_abort_the_source(tmp_path):
    class _FailingEnricher(MetaData):
        def enrich_entity_full(self, data_registry, source, database, collection, entity, attributes, rebuild=False):
            if entity.get("name") == "a_orders":
                raise RuntimeError("boom")
            return super().enrich_entity_full(data_registry, source, database, collection, entity, attributes, rebuild)

    reg = _make_registry(tmp_path, _FailingEnricher(llm_fn=_fake_llm))

    reg.enrich_source_metadata("src", recursive=True)  # must not raise

    # a_orders failed, but b_customers was still enriched.
    assert _entity_desc(reg, "b_customers") == "LLM table description"
