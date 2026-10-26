"""Regression tests for issue #103.

BM25 tokenized on whitespace only, so `order date` never matched `order_date`,
`ship country` never matched `ShipCountry`, and `freight?` never matched `freight`.
Tokenization now splits snake_case / camelCase and strips punctuation.
"""
from blue_data.core.utils.similarity_utils import compute_bm25_score, tokenize_text
from blue_data.registry.data_registry import DataRegistry


# ---------- tokenizer ----------

def test_tokenize_snake_and_camel_and_punctuation():
    assert tokenize_text("order_date") == ["order", "date"]
    assert tokenize_text("ShipCountry") == ["ship", "country"]
    assert tokenize_text("freight?") == ["freight"]
    assert tokenize_text("HTTPServer") == ["http", "server"]
    assert tokenize_text("order date") == ["order", "date"]
    assert tokenize_text("") == []


def test_bm25_matches_across_tokenization_boundaries():
    assert compute_bm25_score("order date", "order_date") > 0
    assert compute_bm25_score("ship country", "ShipCountry") > 0
    assert compute_bm25_score("freight?", "freight") > 0


# ---------- end-to-end through search_records (BM25-only, no vector source) ----------

def _reg():
    reg = DataRegistry()
    for name, desc in [("order_date", ""), ("ShipCountry", ""), ("freight", "the cost of the shipment")]:
        reg.register_source_database_collection_entity_attribute("s", "d", "public", "orders", name, description=desc)
    return reg


def test_search_matches_snake_case_name():
    assert [h["name"] for h in _reg().search_records("order date", type="attribute")] == ["order_date"]


def test_search_matches_camel_case_name():
    assert [h["name"] for h in _reg().search_records("ship country", type="attribute")] == ["ShipCountry"]


def test_search_ignores_trailing_punctuation():
    assert [h["name"] for h in _reg().search_records("freight?", type="attribute")] == ["freight"]
