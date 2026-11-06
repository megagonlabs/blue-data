"""Regression tests for issue #283.

The documented workflow is add → sync → stats → enrich for any registered source.
``DataSource.fetch_property_stats`` returns ``None`` by default, and the attribute
enrichment did ``stats.get("sample_values", [])`` on a value that could be ``None``
(the default hook, and its on-the-fly collect, both return None) — so enrichment
crashed part-way with ``'NoneType' object has no attribute 'get'`` on doc-source and
any source keeping the default. Enrichment must instead give such an attribute no value
semantics and continue. No network / no external services.
"""
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.source import DataSource


class _DefaultStatsSource(DataSource):
    """Keeps the default fetch_property_stats hook (returns None), like doc-source."""

    def _connect(self, **connection):
        return None


def _registry_with_attribute():
    reg = DataRegistry(metadata_enricher=MetaData(llm_fn=None))
    reg.register_source(_DefaultStatsSource("docs"))
    reg.register_source_database("docs", "documents")
    reg.register_source_database_collection("docs", "documents", "c")
    reg.register_source_database_collection_entity("docs", "documents", "c", "ChunkRecord")
    reg.register_source_database_collection_entity_attribute(
        "docs", "documents", "c", "ChunkRecord", "mime_type"
    )
    return reg


def test_default_stats_hook_returns_none():
    assert _DefaultStatsSource("docs").fetch_property_stats("documents", "c", "E", "a") is None


def test_attribute_enrichment_tolerates_none_stats():
    reg = _registry_with_attribute()
    # Pre-fix: raised AttributeError('NoneType' object has no attribute 'get').
    result = reg.enrich_source_database_collection_entity_attribute(
        "docs", "documents", "c", "ChunkRecord", "mime_type"
    )
    assert result is not None  # a value_semantics dict (UNKNOWN), not a crash


def test_enrich_source_completes_with_default_stats():
    reg = _registry_with_attribute()
    reg.enrich_source("docs")  # must not raise
    vs = reg.get_source_database_collection_entity_attribute_property(
        "docs", "documents", "c", "ChunkRecord", "mime_type", "value_semantics"
    )
    assert vs is not None  # the attribute was enriched (with no sample values)


def test_enrich_source_metadata_completes_with_default_stats():
    # The `metadata` command runs enrich_source first, so it hit the same crash (#283).
    reg = _registry_with_attribute()
    reg.enrich_source_metadata("docs")  # must not raise
