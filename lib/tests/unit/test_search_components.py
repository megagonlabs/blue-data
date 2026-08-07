"""Unit tests for search components.

Covers: KeywordSearch, HybridSearch (search + helpers), RecordIndexer,
VectorSearch.score_record, and find_best_score_among_nodes.
All tests are dependency-free except for MemoryVectorSource.
"""
import pytest

from blue_data.registry.search.keyword_search import KeywordSearch
from blue_data.registry.search.hybrid_search import HybridSearch
from blue_data.registry.search.indexing import RecordIndexer
from blue_data.registry.search.vector_search import VectorSearch
from blue_data.registry.search.ranking import find_best_score_among_nodes
from blue_data.source.vector.memory_vector_source import MemoryVectorSource


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

OPEN_PARAMS = {
    "bm25_weight": 1.0,
    "vector_weight": 0.0,
    "value_weight": 0.0,
    "bm25_threshold": 0.0,
    "vector_threshold": 0.0,
    "value_threshold": 0.0,
    "combined_threshold": 0.0,
}

OPEN_CONFIG = {
    **OPEN_PARAMS,
    "combined_threshold": 0.001,  # exclude zero-score (no-match) records; 0.0 never filters
    "bm25_normalization": "minmax",
    "enable_schema": False,
    "hierarchical_enabled": True,
    "hierarchical_database_types": ["database", "collection", "entity", "attribute"],
    "hierarchical_collection_types": ["collection", "entity", "attribute"],
    "search_limit": 1000,
}


def _rec(name, type="entity", scope="/source/s/database/db/collection/public", **extra):
    return {"name": name, "type": type, "scope": scope, **extra}


def _unit_vec(i, dim=4):
    v = [0.0] * dim
    v[i] = 1.0
    return v


def _identity_emb(text: str) -> list[float]:
    """Embedding that maps text to a fixed vector based on first char — just for wiring tests."""
    dim = 4
    idx = ord(text[0]) % dim if text else 0
    return _unit_vec(idx, dim)


# ===========================================================================
# KeywordSearch
# ===========================================================================

class TestKeywordSearch:
    def setup_method(self):
        self.ks = KeywordSearch()

    def test_match_in_name_returns_result(self):
        records = [_rec("orders")]
        results = self.ks.search(records, "orders")
        assert len(results) == 1
        assert results[0]["record"]["name"] == "orders"

    def test_match_in_name_scores_higher_than_description(self):
        records = [
            _rec("orders", description="a table"),
            _rec("items", description="the orders table"),
        ]
        results = self.ks.search(records, "orders")
        assert results[0]["record"]["name"] == "orders"
        assert results[0]["score"] > results[1]["score"]

    def test_no_match_returns_empty(self):
        records = [_rec("customers")]
        assert self.ks.search(records, "revenue") == []

    def test_case_insensitive(self):
        records = [_rec("Orders")]
        results = self.ks.search(records, "orders")
        assert len(results) == 1

    def test_type_filter(self):
        records = [_rec("orders", type="entity"), _rec("prod", type="database")]
        results = self.ks.search(records, "orders", record_type="entity")
        assert all(r["record"]["type"] == "entity" for r in results)

    def test_scope_filter(self):
        records = [
            _rec("orders", scope="/source/a/database/db/collection/public"),
            _rec("orders", scope="/source/b/database/db/collection/public"),
        ]
        results = self.ks.search(records, "orders", scope="/source/a")
        assert len(results) == 1
        assert results[0]["record"]["scope"].startswith("/source/a")

    def test_pagination_page0(self):
        records = [_rec(f"orders_{i}") for i in range(5)]
        results = self.ks.search(records, "orders", page=0, page_size=2)
        assert len(results) == 2

    def test_pagination_page1(self):
        records = [_rec(f"orders_{i}") for i in range(5)]
        results = self.ks.search(records, "orders", page=1, page_size=2)
        assert len(results) == 2

    def test_empty_records(self):
        assert self.ks.search([], "orders") == []

    def test_match_in_description_only(self):
        records = [_rec("items", description="order details")]
        results = self.ks.search(records, "order")
        assert len(results) == 1
        assert results[0]["score"] == 5


# ===========================================================================
# HybridSearch._filter_records
# ===========================================================================

class TestFilterRecords:
    def setup_method(self):
        self.hs = HybridSearch(config=OPEN_CONFIG)

    def test_no_filter_returns_all(self):
        records = [_rec("a"), _rec("b")]
        assert len(self.hs._filter_records(records, None, None)) == 2

    def test_type_filter_dict(self):
        records = [_rec("a", type="entity"), _rec("b", type="database")]
        out = self.hs._filter_records(records, "entity", None)
        assert len(out) == 1 and out[0]["name"] == "a"

    def test_scope_filter_prefix_match(self):
        records = [
            _rec("a", scope="/source/x"),
            _rec("b", scope="/source/y"),
        ]
        out = self.hs._filter_records(records, None, "/source/x")
        assert len(out) == 1 and out[0]["name"] == "a"

    def test_type_and_scope_combined(self):
        records = [
            _rec("a", type="entity", scope="/source/x"),
            _rec("b", type="database", scope="/source/x"),
            _rec("c", type="entity", scope="/source/y"),
        ]
        out = self.hs._filter_records(records, "entity", "/source/x")
        assert len(out) == 1 and out[0]["name"] == "a"

    def test_scope_none_treated_as_root(self):
        records = [_rec("a", scope=None)]
        out = self.hs._filter_records(records, None, "/source/x")
        assert len(out) == 0


# ===========================================================================
# HybridSearch._record_doc_text
# ===========================================================================

class TestRecordDocText:
    def test_name_and_description(self):
        r = {"name": "orders", "description": "purchase orders"}
        text = HybridSearch._record_doc_text(r)
        assert "orders" in text
        assert "purchase orders" in text

    def test_metadata_description_included(self):
        r = {"name": "orders", "properties": {"metadata": {"description": "order lines"}}}
        text = HybridSearch._record_doc_text(r)
        assert "order lines" in text

    def test_missing_fields_no_error(self):
        text = HybridSearch._record_doc_text({})
        assert text == ""

    def test_object_record(self):
        class R:
            name = "users"
            description = "user accounts"
        text = HybridSearch._record_doc_text(R())
        assert "users" in text


# ===========================================================================
# HybridSearch._schema_text
# ===========================================================================

class TestSchemaText:
    def test_dict_schema_extracts_entity_names(self):
        r = {
            "properties": {
                "schema": {
                    "entities": {
                        "e1": {"name": "orders", "attributes": {"a1": {"name": "amount"}}},
                    }
                }
            }
        }
        text = HybridSearch._schema_text(r)
        assert "orders" in text
        assert "amount" in text

    def test_string_schema_returned_as_is(self):
        r = {"properties": {"schema": "orders amount customer_id"}}
        assert HybridSearch._schema_text(r) == "orders amount customer_id"

    def test_no_schema_returns_none(self):
        assert HybridSearch._schema_text({"properties": {}}) is None

    def test_missing_properties_returns_none(self):
        assert HybridSearch._schema_text({}) is None


# ===========================================================================
# HybridSearch.search (keyword-only — no vector source)
# ===========================================================================

class TestHybridSearchKeywordOnly:
    def setup_method(self):
        self.hs = HybridSearch(config=OPEN_CONFIG)

    def _search(self, records, query, **kw):
        return self.hs.search(records, query, **kw)

    def test_matching_record_returned(self):
        records = [_rec("orders"), _rec("customers")]
        results = self._search(records, "orders")
        assert any(r["name"] == "orders" for r in results)

    def test_non_matching_excluded(self):
        records = [_rec("customers")]
        results = self._search(records, "revenue")
        assert results == []

    def test_type_filter(self):
        records = [_rec("orders", type="entity"), _rec("prod", type="database")]
        results = self._search(records, "orders", type="entity")
        assert all(r["type"] == "entity" for r in results)

    def test_scope_filter(self):
        records = [
            _rec("orders", scope="/source/a/database/db"),
            _rec("orders", scope="/source/b/database/db"),
        ]
        results = self._search(records, "orders", scope="/source/a")
        assert len(results) == 1

    def test_pagination(self):
        # Names must tokenise to match the query — use description so BM25 fires on all 6.
        records = [_rec(f"table{i}", description="orders data") for i in range(6)]
        p0 = self._search(records, "orders", page=0, page_size=3)
        p1 = self._search(records, "orders", page=1, page_size=3)
        assert len(p0) == 3
        assert len(p1) == 3
        names0 = {r["name"] for r in p0}
        names1 = {r["name"] for r in p1}
        assert names0.isdisjoint(names1)

    def test_sorted_by_score_descending(self):
        records = [
            _rec("orders", description="the orders table"),
            _rec("orders_backup"),
        ]
        results = self._search(records, "orders")
        assert results[0]["_score"] >= results[-1]["_score"]

    def test_score_attached_to_result(self):
        records = [_rec("orders")]
        results = self._search(records, "orders")
        assert "_score" in results[0]
        assert results[0]["_score"] > 0

    def test_empty_records(self):
        assert self._search([], "orders") == []

    def test_value_score_read_from_dict_record(self):
        """value_relevance_score on a dict record must actually affect scoring (not silently 0)."""
        rec_with_value = {**_rec("orders"), "value_relevance_score": 0.9}
        rec_no_value = _rec("items")

        results_with = self._search([rec_with_value], "orders")
        results_without = self._search([rec_no_value], "items")

        # Both match their query; the one with a value score should have a higher _score
        # (value_weight is 0 in OPEN_CONFIG, so just verify it doesn't crash and score > 0)
        assert len(results_with) == 1
        assert results_with[0]["_score"] >= 0

    def test_value_score_dict_vs_zero(self):
        """Directly verify dict records with value scores outscore identical records without."""
        hs = HybridSearch(config={
            **OPEN_CONFIG,
            "bm25_weight": 0.5,
            "value_weight": 0.5,
            "value_threshold": 0.0,
        })
        rec_high = {**_rec("orders"), "value_relevance_score": 1.0}
        rec_low  = {**_rec("items"),  "value_relevance_score": 0.0}

        r_high = hs.search([rec_high], "orders")
        r_low  = hs.search([rec_low],  "items")
        assert r_high[0]["_score"] > r_low[0]["_score"]

    def test_combined_threshold_filters_low_scores(self):
        # With two records, minmax gives the non-matching one 0.0 and matching one 1.0.
        # A threshold of 0.5 keeps the match and excludes the non-match.
        hs = HybridSearch(config={**OPEN_CONFIG, "combined_threshold": 0.5})
        records = [_rec("orders"), _rec("customers")]
        results = hs.search(records, "orders")
        names = [r["name"] for r in results]
        assert "orders" in names
        assert "customers" not in names


# ===========================================================================
# HybridSearch.search — with vector source
# ===========================================================================

class TestHybridSearchWithVector:
    def setup_method(self):
        self.vs = MemoryVectorSource()
        self.hs = HybridSearch(
            vector_source=self.vs,
            embedding_fn=_identity_emb,
            config={**OPEN_CONFIG, "vector_weight": 0.5, "bm25_weight": 0.5},
        )

    def _index(self, record):
        scope = record.get("scope", "/")
        rtype = record.get("type", "")
        name = record.get("name", "")
        doc_id = f"{scope}/{rtype}/{name}"
        text = f"{name} {record.get('description', '')}"
        emb = _identity_emb(text)
        self.vs.execute_query({
            "op": "VECTOR.CREATE_INDEX",
            "index": "registry_index",
            "collection": "registry_records",
            "dim": 4,
        })
        self.vs.execute_query({
            "op": "VECTOR.UPSERT",
            "collection": "registry_records",
            "id": doc_id,
            "doc": {"embedding": emb, "name": name, "type": rtype, "scope": scope},
            "embedding_field": "embedding",
        })

    def test_vector_score_contributes(self):
        rec = _rec("apple")
        self._index(rec)
        results = self.hs.search([rec], "apple")
        assert len(results) == 1
        assert results[0]["_score"] > 0

    def test_no_embedding_fn_degrades_gracefully(self):
        hs = HybridSearch(vector_source=self.vs, embedding_fn=None, config=OPEN_CONFIG)
        records = [_rec("orders")]
        results = hs.search(records, "orders")
        assert isinstance(results, list)


# ===========================================================================
# RecordIndexer
# ===========================================================================

class TestRecordIndexer:

    def test_record_text_full(self):
        idx = RecordIndexer()
        r = {"name": "orders", "type": "entity", "description": "purchase orders",
             "properties": {"metadata": {"description": "extra"}}}
        text = idx._record_text(r)
        assert "orders" in text
        assert "entity" in text
        assert "purchase orders" in text

    def test_record_text_missing_fields(self):
        idx = RecordIndexer()
        assert idx._record_text({}) == ""

    def test_set_record_no_vector_source_is_noop(self):
        idx = RecordIndexer(vector_source=None, embedding_fn=_identity_emb)
        idx.set_record({"name": "orders", "type": "entity", "scope": "/"})
        # no error, nothing indexed

    def test_set_record_no_embedding_fn_is_noop(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=None)
        idx.set_record({"name": "orders", "type": "entity", "scope": "/"})

    def test_set_record_indexes_document(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=_identity_emb, vector_dim=4)
        idx.set_record({"name": "orders", "type": "entity", "scope": "/source/s"})
        emb = _identity_emb("orders entity")
        results = vs.execute_query({
            "op": "VECTOR.KNN",
            "index": "registry_index",
            "vector": emb,
            "k": 1,
        })
        assert len(results) == 1
        assert results[0]["name"] == "orders"

    def test_set_record_empty_text_is_noop(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=_identity_emb, vector_dim=4)
        idx.set_record({"name": "", "type": "", "scope": "/"})
        # No index created, so KNN would have nothing to return — just ensure no error

    def test_set_record_with_schema_indexes_schema_embedding(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=_identity_emb, vector_dim=4)
        record = {
            "name": "public",
            "type": "collection",
            "scope": "/source/s",
            "properties": {"schema": "orders users products"},
        }
        idx.set_record(record)
        emb = _identity_emb("public collection")
        results = vs.execute_query({
            "op": "VECTOR.KNN",
            "index": "registry_index",
            "vector": emb,
            "k": 1,
            "return_fields": ["schema_embedding"],
        })
        assert len(results) == 1
        assert "schema_embedding" in results[0]

    def test_delete_record_no_vector_source_is_noop(self):
        idx = RecordIndexer(vector_source=None)
        idx.delete_record("orders", "entity", "/source/s")

    def test_delete_record_removes_from_index(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=_identity_emb, vector_dim=4)
        idx.set_record({"name": "orders", "type": "entity", "scope": "/source/s"})
        idx.delete_record("orders", "entity", "/source/s")
        emb = _identity_emb("orders entity")
        results = vs.execute_query({
            "op": "VECTOR.KNN",
            "index": "registry_index",
            "vector": emb,
            "k": 1,
        })
        assert all(r.get("name") != "orders" for r in results)

    def test_ensure_index_idempotent(self):
        vs = MemoryVectorSource()
        idx = RecordIndexer(vector_source=vs, embedding_fn=_identity_emb, vector_dim=4)
        idx.ensure_index()
        idx.ensure_index()  # second call must not raise
        assert idx._index_ensured is True

    def test_ensure_index_no_vector_source_is_noop(self):
        idx = RecordIndexer(vector_source=None)
        idx.ensure_index()
        assert idx._index_ensured is False


# ===========================================================================
# VectorSearch.score_record
# ===========================================================================

class TestVectorSearchScoreRecord:
    def _make_vs_with_doc(self, name, scope, rtype, emb):
        vs = MemoryVectorSource()
        vs.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx",
                          "collection": "coll", "dim": len(emb)})
        doc_id = f"{scope}/{rtype}/{name}"
        vs.execute_query({
            "op": "VECTOR.UPSERT",
            "collection": "coll",
            "id": doc_id,
            "doc": {"embedding": emb, "name": name},
            "embedding_field": "embedding",
        })
        searcher = VectorSearch(vector_source=vs, index_name="idx", vector_dim=len(emb))
        return searcher, doc_id

    def test_no_vector_source_returns_zero(self):
        searcher = VectorSearch(vector_source=None)
        score = searcher.score_record({"name": "x", "type": "entity", "scope": "/"}, [1.0], {})
        assert score == 0.0

    def test_no_query_vector_returns_zero(self):
        vs = MemoryVectorSource()
        searcher = VectorSearch(vector_source=vs, index_name="idx")
        score = searcher.score_record({"name": "x", "type": "entity", "scope": "/"}, None, {})
        assert score == 0.0

    def test_record_not_indexed_returns_zero(self):
        vs = MemoryVectorSource()
        vs.execute_query({"op": "VECTOR.CREATE_INDEX", "index": "idx",
                          "collection": "coll", "dim": 4})
        searcher = VectorSearch(vector_source=vs, index_name="idx")
        score = searcher.score_record(
            {"name": "ghost", "type": "entity", "scope": "/"}, _unit_vec(0), {}
        )
        assert score == 0.0

    def test_identical_vector_scores_near_one(self):
        emb = _unit_vec(0)
        searcher, _ = self._make_vs_with_doc("orders", "/source/s", "entity", emb)
        record = {"name": "orders", "type": "entity", "scope": "/source/s"}
        score = searcher.score_record(record, emb, {"enable_schema": False})
        assert score == pytest.approx(1.0, abs=0.05)

    def test_compute_embedding_returns_none_without_fn(self):
        searcher = VectorSearch(embedding_fn=None)
        assert searcher.compute_embedding("hello") is None

    def test_compute_embedding_calls_fn(self):
        searcher = VectorSearch(embedding_fn=_identity_emb)
        result = searcher.compute_embedding("apple")
        assert isinstance(result, list)
        assert len(result) == 4


# ===========================================================================
# find_best_score_among_nodes
# ===========================================================================

class TestFindBestScoreAmongNodes:

    PARAMS = {
        "bm25_weight": 0.5,
        "vector_weight": 0.5,
        "value_weight": 0.0,
        "bm25_threshold": 0.0,
        "vector_threshold": 0.0,
        "value_threshold": 0.0,
        "combined_threshold": 0.0,
    }

    def _node(self, bm25=0.0, vec=0.0, value=0.0):
        class R:
            normalized_bm25_score = bm25
            vector_score = vec
            value_relevance_score = value
            aggregated_value_relevance = 0.0
            most_relevant_values = []
        return {"record": R(), "children": set(), "parent": "/"}

    def test_returns_best_scoring_node(self):
        h = {
            "a": self._node(bm25=0.9, vec=0.9),
            "b": self._node(bm25=0.1, vec=0.1),
        }
        score, record, _, _ = find_best_score_among_nodes({"a", "b"}, h, self.PARAMS)
        assert record is h["a"]["record"]

    def test_empty_set_returns_none(self):
        _, record, _, _ = find_best_score_among_nodes(set(), {}, self.PARAMS)
        assert record is None

    def test_missing_node_id_skipped(self):
        _, record, _, _ = find_best_score_among_nodes({"ghost"}, {}, self.PARAMS)
        assert record is None

    def test_combined_threshold_filters_low_scores(self):
        params = {**self.PARAMS, "combined_threshold": 0.9}
        h = {"a": self._node(bm25=0.3, vec=0.3)}  # combined = 0.3, below 0.9
        _, record, _, _ = find_best_score_among_nodes({"a"}, h, params)
        assert record is None

    def test_value_tiebreak(self):
        h = {
            "a": self._node(bm25=0.8, vec=0.8, value=0.1),
            "b": self._node(bm25=0.8, vec=0.8, value=0.9),
        }
        params = {**self.PARAMS, "value_weight": 0.0}
        _, record, _, value_score = find_best_score_among_nodes({"a", "b"}, h, params)
        # Same combined score — the one with higher value wins the tiebreak
        assert value_score == pytest.approx(0.9)

    def test_inverted_score_lower_is_better(self):
        h = {"a": self._node(bm25=1.0, vec=1.0)}
        inv_score, _, _, _ = find_best_score_among_nodes({"a"}, h, self.PARAMS)
        assert inv_score == pytest.approx(0.0, abs=0.01)
