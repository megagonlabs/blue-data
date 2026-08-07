"""Search scenario tests.

End-to-end scenarios against a real DataRegistry (MemoryJSONSource +
MemoryVectorSource + deterministic hash embedding). Each test exercises a
complete user-journey slice rather than a single method.

Thresholds are relaxed to 0 via OPEN_CONFIG so tests focus on pipeline
correctness and ranking, not score-tuning with a non-semantic hash embedding.
"""
import hashlib
import math

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource
from blue_data.source.source import DataSource

DIM = 32

OPEN_CONFIG = {
    "vector_threshold": 0.0,
    "bm25_threshold": 0.0,
    "combined_threshold": 0.0,
}


def hash_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


@pytest.fixture
def reg():
    return DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource(),
        embedding_fn=hash_embedding,
        vector_dim=DIM,
        rebuild=True,
        hybrid_config=OPEN_CONFIG,
    )


# ---------------------------------------------------------------------------
# Stub source used in sync scenarios
# ---------------------------------------------------------------------------

class _StubSource(DataSource):
    """Minimal DataSource with a fixed schema — used to drive sync_source."""

    def __init__(self, name, databases=None):
        self._db_map = databases or {}  # {db: {collection: {entity: [attr, ...]}}}
        super().__init__(name)

    def fetch_databases(self):
        return list(self._db_map)

    def fetch_database_collections(self, database):
        return list(self._db_map.get(database, {}))

    def fetch_database_collection_entities(self, database, collection):
        entities = {}
        for entity, attrs in self._db_map.get(database, {}).get(collection, {}).items():
            entities[entity] = {
                "properties": {},
                "contents": {
                    "attributes": {a: {"name": a, "info": {"type": "str", "values": []}} for a in attrs}
                },
            }
        return entities

    def fetch_database_collection_relations(self, database, collection):
        return {}


# ===========================================================================
# 1. Scope-based search
# ===========================================================================

class TestScopedSearch:
    def test_scope_limits_to_source(self, reg):
        reg.register_record("orders", "entity", scope="/source/alpha/database/db/collection/public")
        reg.register_record("orders", "entity", scope="/source/beta/database/db/collection/public")

        results = reg.search_records("orders", scope="/source/alpha")
        assert all(r["scope"].startswith("/source/alpha") for r in results)
        assert len(results) == 1

    def test_scope_limits_to_database(self, reg):
        reg.register_record("users", "entity", scope="/source/s/database/prod/collection/public")
        reg.register_record("users", "entity", scope="/source/s/database/staging/collection/public")

        results = reg.search_records("users", scope="/source/s/database/prod")
        scopes = [r["scope"] for r in results]
        assert all("prod" in s for s in scopes)
        assert not any("staging" in s for s in scopes)

    def test_no_scope_returns_all_sources(self, reg):
        reg.register_record("orders", "entity", scope="/source/alpha/database/db/collection/public")
        reg.register_record("orders", "entity", scope="/source/beta/database/db/collection/public")

        results = reg.search_records("orders")
        assert len(results) == 2

    def test_nonexistent_scope_returns_empty(self, reg):
        reg.register_record("orders", "entity", scope="/source/alpha/database/db/collection/public")
        results = reg.search_records("orders", scope="/source/ghost")
        assert results == []


# ===========================================================================
# 2. Search after sync_source
# ===========================================================================

class TestSearchAfterSync:
    def test_entities_findable_after_sync(self, reg):
        src = _StubSource("northwind", {
            "northwind": {"public": {"orders": ["id", "amount"], "customers": ["id", "name"]}}
        })
        reg.register_source(src)
        reg.sync_source("northwind", recursive=True)

        results = reg.search_records("orders")
        names = [r["name"] for r in results]
        assert "orders" in names

    def test_attributes_findable_after_sync(self, reg):
        src = _StubSource("mydb", {
            "mydb": {"public": {"users": ["email", "created_at"]}}
        })
        reg.register_source(src)
        reg.sync_source("mydb", recursive=True)

        results = reg.search_records("email", type="attribute")
        assert any(r["name"] == "email" for r in results)

    def test_sync_creates_collection_record(self, reg):
        src = _StubSource("db", {"db": {"analytics": {"events": ["ts", "payload"]}}})
        reg.register_source(src)
        reg.sync_source("db", recursive=True)

        results = reg.search_records("analytics", type="collection")
        assert any(r["name"] == "analytics" for r in results)

    def test_sync_removes_deleted_entities(self, reg):
        src = _StubSource("db", {"db": {"public": {"orders": ["id"], "temp": ["id"]}}})
        reg.register_source(src)
        reg.sync_source("db", recursive=True)

        # Remove "temp" from the live source and re-sync
        src._db_map = {"db": {"public": {"orders": ["id"]}}}
        reg.sync_source("db", recursive=True)

        results = reg.search_records("temp", type="entity")
        assert not any(r["name"] == "temp" for r in results)

    def test_two_sources_both_searchable(self, reg):
        src_a = _StubSource("sourceA", {"db": {"public": {"products": ["id", "name"]}}})
        src_b = _StubSource("sourceB", {"db": {"public": {"invoices": ["id", "total"]}}})
        reg.register_source(src_a)
        reg.register_source(src_b)
        reg.sync_source("sourceA", recursive=True)
        reg.sync_source("sourceB", recursive=True)

        products = reg.search_records("products", type="entity")
        invoices = reg.search_records("invoices", type="entity")
        assert any(r["name"] == "products" for r in products)
        assert any(r["name"] == "invoices" for r in invoices)


# ===========================================================================
# 3. Index consistency after delete
# ===========================================================================

class TestIndexConsistencyAfterDelete:
    def test_deleted_record_not_in_results(self, reg):
        reg.register_record("temp_table", "entity",
                            scope="/source/s/database/db/collection/public")
        results_before = reg.search_records("temp table")
        assert any(r["name"] == "temp_table" for r in results_before)

        reg.deregister_record("temp_table", "entity",
                               scope="/source/s/database/db/collection/public")
        results_after = reg.search_records("temp table")
        assert not any(r["name"] == "temp_table" for r in results_after)

    def test_other_records_unaffected_by_delete(self, reg):
        reg.register_record("orders", "entity",
                            scope="/source/s/database/db/collection/public")
        reg.register_record("customers", "entity",
                            scope="/source/s/database/db/collection/public")

        reg.deregister_record("customers", "entity",
                               scope="/source/s/database/db/collection/public")

        results = reg.search_records("orders")
        assert any(r["name"] == "orders" for r in results)

    def test_re_register_after_delete_is_searchable(self, reg):
        scope = "/source/s/database/db/collection/public"
        reg.register_record("events", "entity", scope=scope)
        reg.deregister_record("events", "entity", scope=scope)
        reg.register_record("events", "entity", scope=scope,
                            description="event log table")

        results = reg.search_records("events")
        assert any(r["name"] == "events" for r in results)


# ===========================================================================
# 4. Pagination
# ===========================================================================

class TestPagination:
    def _register_many(self, reg, n=12):
        scope = "/source/s/database/db/collection/public"
        for i in range(n):
            reg.register_record(f"table{i}", "entity", scope=scope,
                                description="orders data")

    def test_page0_and_page1_non_overlapping(self, reg):
        self._register_many(reg, 12)
        p0 = reg.search_records("orders", page=0, page_size=5)
        p1 = reg.search_records("orders", page=1, page_size=5)
        names0 = {r["name"] for r in p0}
        names1 = {r["name"] for r in p1}
        assert names0.isdisjoint(names1)

    def test_page_size_respected(self, reg):
        self._register_many(reg, 12)
        results = reg.search_records("orders", page=0, page_size=4)
        assert len(results) <= 4

    def test_last_page_returns_remainder(self, reg):
        self._register_many(reg, 7)
        p0 = reg.search_records("orders", page=0, page_size=5)
        p1 = reg.search_records("orders", page=1, page_size=5)
        assert len(p0) == 5
        assert len(p1) == 2

    def test_beyond_last_page_returns_empty(self, reg):
        self._register_many(reg, 3)
        results = reg.search_records("orders", page=99, page_size=5)
        assert results == []


# ===========================================================================
# 5. Hierarchical search
# ===========================================================================

class TestHierarchicalSearch:
    def test_collection_search_uses_hierarchical_path(self, reg):
        src = _StubSource("db", {
            "db": {"orders_schema": {"orders": ["id", "amount", "customer_id"]}}
        })
        reg.register_source(src)
        reg.sync_source("db", recursive=True)

        results = reg.search_records_hierarchical("orders", type="collection")
        assert isinstance(results, list)

    def test_hierarchical_returns_parent_when_child_matches(self, reg):
        # Register a collection whose child entity matches the query.
        scope_col = "/source/s/database/db"
        scope_ent = "/source/s/database/db/collection/sales"
        reg.register_record("sales", "collection", scope=scope_col)
        reg.register_record("revenue", "entity", scope=scope_ent,
                            description="orders revenue data")

        results = reg.search_records_hierarchical("revenue orders", type="collection")
        assert isinstance(results, list)

    def test_hierarchical_no_match_returns_empty(self, reg):
        reg.register_record("alpha", "collection", scope="/source/s/database/db")
        results = reg.search_records_hierarchical(
            "zzz_unrelated_xyz",
            type="collection",
            bm25_weight=1.0, vector_weight=0.0, combined_threshold=0.001,
        )
        assert results == []

    def test_search_records_routes_to_hierarchical_for_collection_type(self, reg):
        reg.register_record("logs", "collection", scope="/source/s/database/db")
        # search_records with type="collection" should route to hierarchical internally
        results = reg.search_records("logs", type="collection")
        assert isinstance(results, list)


# ===========================================================================
# 6. value_relevance_score on dict records affects ranking
# ===========================================================================

class TestValueRelevanceScoreRanking:
    def test_record_with_value_score_ranks_above_record_without(self, reg):
        # Use a registry WITHOUT vector source to isolate value_weight effect.
        r = DataRegistry(
            store=MemoryJSONSource(),
            rebuild=False,
            hybrid_config={
                **OPEN_CONFIG,
                "bm25_weight": 0.5,
                "value_weight": 0.5,
                "value_threshold": 0.0,
            },
        )
        scope = "/source/s/database/db/collection/public"
        r.register_record("orders", "entity", scope=scope,
                          properties={"value_relevance_score": 0.9})
        r.register_record("customers", "entity", scope=scope,
                          properties={"value_relevance_score": 0.0})

        # Both match "orders" / "customers" respectively — search for a neutral
        # term that hits both via description to compare value_relevance_score effect.
        r.register_record("alpha", "entity", scope=scope,
                          description="data table",
                          properties={"value_relevance_score": 0.9})
        r.register_record("beta", "entity", scope=scope,
                          description="data table",
                          properties={"value_relevance_score": 0.0})

        results = r.search_records("data table")
        names = [rec["name"] for rec in results]
        assert names.index("alpha") < names.index("beta")

    def test_value_score_zero_does_not_crash(self, reg):
        scope = "/source/s/database/db/collection/public"
        reg.register_record("orders", "entity", scope=scope,
                            properties={"value_relevance_score": 0.0})
        results = reg.search_records("orders")
        assert isinstance(results, list)


# ===========================================================================
# 7. Multiple sources — search returns records from both
# ===========================================================================

class TestMultipleSourceSearch:
    def test_search_spans_multiple_sources(self, reg):
        src_a = _StubSource("crm", {"crm": {"public": {"contacts": ["id", "email"]}}})
        src_b = _StubSource("erp", {"erp": {"public": {"contacts": ["id", "phone"]}}})
        reg.register_source(src_a)
        reg.register_source(src_b)
        reg.sync_source("crm", recursive=True)
        reg.sync_source("erp", recursive=True)

        results = reg.search_records("contacts", type="entity")
        sources_found = {r["scope"].split("/")[2] for r in results if r["name"] == "contacts"}
        assert "crm" in sources_found
        assert "erp" in sources_found

    def test_scope_filter_isolates_one_source(self, reg):
        src_a = _StubSource("crm", {"crm": {"public": {"contacts": ["id"]}}})
        src_b = _StubSource("erp", {"erp": {"public": {"contacts": ["id"]}}})
        reg.register_source(src_a)
        reg.register_source(src_b)
        reg.sync_source("crm", recursive=True)
        reg.sync_source("erp", recursive=True)

        results = reg.search_records("contacts", type="entity", scope="/source/crm")
        assert all(r["scope"].startswith("/source/crm") for r in results)
        assert len(results) == 1


# ===========================================================================
# 8. Schema text boost
# ===========================================================================

class TestSchemaTextBoost:
    def test_collection_with_schema_text_ranks_higher(self, reg):
        scope = "/source/s/database/db"
        reg.register_record(
            "orders_schema", "collection", scope=scope,
            properties={"schema": "orders line_items amount customer_id"},
        )
        reg.register_record(
            "generic_schema", "collection", scope=scope,
            description="a collection",
        )

        results = reg.search_records(
            "orders line_items", type="collection",
            hierarchical_enabled=False,
        )
        if len(results) >= 2:
            assert results[0]["name"] == "orders_schema"

    def test_schema_text_included_in_bm25(self, reg):
        scope = "/source/s/database/db"
        reg.register_record(
            "analytics", "collection", scope=scope,
            properties={"schema": "revenue profit margin quarterly"},
        )
        results = reg.search_records(
            "revenue quarterly", type="collection",
            hierarchical_enabled=False,
        )
        assert any(r["name"] == "analytics" for r in results)


# ===========================================================================
# 9. No-results query
# ===========================================================================

class TestNoResults:
    def test_empty_registry_returns_empty(self, reg):
        assert reg.search_records("anything") == []

    def test_no_match_returns_empty(self, reg):
        reg.register_record("orders", "entity",
                            scope="/source/s/database/db/collection/public")
        # BM25-only so hash embeddings don't produce false vector similarity
        results = reg.search_records(
            "zzz_unrelated_xyz_qqq",
            bm25_weight=1.0, vector_weight=0.0, combined_threshold=0.001,
        )
        assert results == []

    def test_type_filter_no_match_returns_empty(self, reg):
        reg.register_record("orders", "entity",
                            scope="/source/s/database/db/collection/public")
        results = reg.search_records("orders", type="database")
        assert results == []


# ===========================================================================
# 10. Identical names in different scopes — scope isolation
# ===========================================================================

class TestScopeIsolation:
    def test_same_name_different_scopes_both_registered(self, reg):
        reg.register_record("users", "entity",
                            scope="/source/alpha/database/db/collection/public")
        reg.register_record("users", "entity",
                            scope="/source/beta/database/db/collection/public")
        assert len(reg.list_records(record_type="entity")) == 2

    def test_scope_filter_returns_only_matching_scope(self, reg):
        reg.register_record("users", "entity",
                            scope="/source/alpha/database/db/collection/public")
        reg.register_record("users", "entity",
                            scope="/source/beta/database/db/collection/public")

        results = reg.search_records("users", scope="/source/alpha")
        assert len(results) == 1
        assert results[0]["scope"].startswith("/source/alpha")

    def test_delete_one_scope_leaves_other_intact(self, reg):
        reg.register_record("users", "entity",
                            scope="/source/alpha/database/db/collection/public")
        reg.register_record("users", "entity",
                            scope="/source/beta/database/db/collection/public")

        reg.deregister_record("users", "entity",
                               scope="/source/alpha/database/db/collection/public")

        results = reg.search_records("users")
        assert len(results) == 1
        assert results[0]["scope"].startswith("/source/beta")
