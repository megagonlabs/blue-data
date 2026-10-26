"""Regression tests for issue #102.

With type="database"/"collection" and no vector source, search_records switched to
a whole-query substring KeywordSearch and returned a {'record','score'} shape, so
multi-word queries found nothing and callers saw a different shape. The scope filter
was also a raw prefix, so scope='/source/db' matched '/source/db2'. All types now
score through the hybrid (BM25) engine with a record+_score shape, and scope matches
on path boundaries. In-memory store, no vector source.
"""
from blue_data.registry.data_registry import DataRegistry


def _reg():
    reg = DataRegistry()
    reg.register_source_database("db", "sales", description="sales ledger database")
    reg.register_source_database("db2", "hr", description="hr database")
    reg.register_source_database_collection_entity("db", "sales", "public", "orders", description="orders")
    reg.register_source_database_collection_entity("db2", "hr", "public", "orders", description="orders")
    return reg


def test_database_search_returns_record_shape_with_score():
    hits = _reg().search_records("sales", type="database")
    assert hits
    top = hits[0]
    assert top["name"] == "sales" and top["type"] == "database"
    assert "_score" in top
    assert "record" not in top and "score" not in top  # not the old shape


def test_database_search_is_bm25_not_substring_match():
    # Non-contiguous multi-word query: a substring match would miss it.
    names = [r["name"] for r in _reg().search_records("ledger sales", type="database")]
    assert "sales" in names


def test_entity_and_database_share_result_shape():
    reg = _reg()
    entity = reg.search_records("orders", type="entity")[0]
    database = reg.search_records("sales", type="database")[0]
    base = {"name", "type", "scope", "description", "_score"}
    assert base <= set(entity)
    assert base <= set(database)


def test_scope_filter_matches_on_path_boundary():
    scopes = [r["scope"] for r in _reg().search_records("orders", type="entity", scope="/source/db")]
    assert scopes == ["/source/db/database/sales/collection/public"]


def test_scope_filter_exact_match_included():
    # The scope value itself (not just descendants) should match.
    reg = _reg()
    names = [r["name"] for r in reg.search_records("sales", type="database", scope="/source/db")]
    assert names == ["sales"]
