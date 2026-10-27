"""Regression tests for issue #82.

The get_enriched_metadata NL tool claimed to expose semantic types, value semantics,
domain concepts, aggregation hints, etc., but returned only
record["properties"]["metadata"]. It now returns all the enrichment written under
record["properties"].
"""
from blue_data.registry.data_registry import DataRegistry


def _reg_with_enriched_attribute():
    reg = DataRegistry()
    reg.register_source_database_collection_entity("s", "d", "public", "orders")
    reg.register_source_database_collection_entity_attribute("s", "d", "public", "orders", "freight")

    def _set(key, value):
        reg.set_source_database_collection_entity_attribute_property(
            "s", "d", "public", "orders", "freight", key, value
        )

    _set("metadata", {"description": "freight cost"})
    _set("value_semantics", {"semantic_type": "CURRENCY_AMOUNT", "source": "llm"})
    _set("domain_concept", {"concept": "CONCEPT.FINANCE.AMOUNT"})
    _set("semantic_role", {"role": "EVIDENCE"})
    _set("safe_aggregation", {"can_sum": True})
    return reg


def test_returns_semantic_enrichment_not_only_metadata():
    reg = _reg_with_enriched_attribute()

    result = reg.get_enriched_metadata("s", "d", "public", "orders", "freight")

    # Everything the tool description promises, not just metadata.
    assert result["metadata"] == {"description": "freight cost"}
    assert result["value_semantics"]["semantic_type"] == "CURRENCY_AMOUNT"
    assert result["domain_concept"]["concept"] == "CONCEPT.FINANCE.AMOUNT"
    assert result["semantic_role"]["role"] == "EVIDENCE"
    assert result["safe_aggregation"]["can_sum"] is True


def test_excludes_non_enrichment_properties():
    reg = _reg_with_enriched_attribute()
    reg.set_source_database_collection_entity_attribute_property(
        "s", "d", "public", "orders", "freight", "info", {"type": "REAL"}
    )
    result = reg.get_enriched_metadata("s", "d", "public", "orders", "freight")
    assert "info" not in result  # raw column type is not enrichment


def test_missing_record_returns_empty():
    reg = DataRegistry()
    assert reg.get_enriched_metadata("s", "d", "public", "orders", "ghost") == {}


def test_entity_level_enrichment():
    reg = DataRegistry()
    reg.register_source_database_collection_entity("s", "d", "public", "orders")
    reg.set_source_database_collection_entity_property(
        "s", "d", "public", "orders", "process_semantics", {"is_event": True}
    )
    result = reg.get_enriched_metadata("s", "d", "public", "orders")
    assert result["process_semantics"] == {"is_event": True}
