"""Tests for BayesianNetworkSource.

Fixtures build a tiny two-node BN (Weather → Umbrella) in a temp directory
using the same save_pgmpy_model helper that production code uses, so we test
the full load/infer round-trip without any mocking.
"""
import json
import os
import pytest

pgmpy = pytest.importorskip("pgmpy", reason="pgmpy not installed (pip install 'blue-data[bn]')")
from pgmpy.models import BayesianNetwork as DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD

from blue_data.source.network.bn.bn_utils import save_pgmpy_model
from blue_data.source.network.bn.bayesian_network_source import BayesianNetworkSource


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _build_weather_model() -> DiscreteBayesianNetwork:
    """Weather (sunny/rainy) → Umbrella (yes/no)."""
    model = DiscreteBayesianNetwork([("Weather", "Umbrella")])
    cpd_weather = TabularCPD(
        "Weather", 2, [[0.7], [0.3]],
        state_names={"Weather": ["sunny", "rainy"]},
    )
    cpd_umbrella = TabularCPD(
        "Umbrella", 2,
        [[0.9, 0.2],   # no:  P(no|sunny)=0.9, P(no|rainy)=0.2
         [0.1, 0.8]],  # yes: P(yes|sunny)=0.1, P(yes|rainy)=0.8
        evidence=["Weather"], evidence_card=[2],
        state_names={"Umbrella": ["no", "yes"], "Weather": ["sunny", "rainy"]},
    )
    model.add_cpds(cpd_weather, cpd_umbrella)
    assert model.check_model()
    return model


@pytest.fixture
def model_dir(tmp_path):
    """Save a Weather→Umbrella BN into tmp_path/default/weather/."""
    collection_dir = tmp_path / "default" / "weather"
    save_pgmpy_model(_build_weather_model(), str(collection_dir))
    return tmp_path


@pytest.fixture
def src(model_dir):
    return BayesianNetworkSource(
        name="test_bn",
        properties={"connection": {"source_directory": str(model_dir)}},
    )


# ---------------------------------------------------------------------------
# Database / collection discovery
# ---------------------------------------------------------------------------

def test_fetch_databases_includes_default(src):
    dbs = src.fetch_databases()
    assert "default" in dbs


def test_fetch_database_collections(src):
    cols = src.fetch_database_collections("default")
    assert "weather" in cols


def test_create_database(src, tmp_path):
    result = src.create_database("new_db")
    assert result["status"] == "success"
    assert "new_db" in src.fetch_databases()


def test_create_database_overwrite(src):
    src.create_database("tmp_db")
    result = src.create_database("tmp_db", overwrite=True)
    assert result["status"] == "success"


def test_create_database_no_overwrite_skips(src):
    src.create_database("x_db")
    result = src.create_database("x_db", overwrite=False)
    assert result["status"] == "skipped"


def test_fetch_database_metadata(src):
    meta = src.fetch_database_metadata("default")
    assert meta["database"] == "default"
    assert meta["collection_count"] >= 1


def test_fetch_collection_metadata(src):
    meta = src.fetch_database_collection_metadata("default", "weather")
    assert meta["node_count"] == 2
    assert meta["edge_count"] == 1


# ---------------------------------------------------------------------------
# Entity / graph structure
# ---------------------------------------------------------------------------

def test_fetch_entities_returns_nodes(src):
    entities = src.fetch_database_collection_entities("default", "weather")
    assert "Weather" in entities
    assert "Umbrella" in entities


def test_fetch_entities_includes_graph_structure(src):
    entities = src.fetch_database_collection_entities("default", "weather")
    umbrella = entities["Umbrella"]
    gs = umbrella.get("properties", {}).get("graph_structure", {})
    assert "Weather" in gs.get("parents", [])


def test_fetch_relations_empty(src):
    assert src.fetch_database_collection_relations("default", "weather") == {}


def test_fetch_nodes_via_network_interface(src):
    nodes = src.fetch_nodes("weather")
    assert set(nodes) == {"Weather", "Umbrella"}


def test_fetch_edges_via_network_interface(src):
    edges = src.fetch_edges("weather")
    assert len(edges) == 1
    assert edges[0]["source"] == "Weather"
    assert edges[0]["target"] == "Umbrella"


# ---------------------------------------------------------------------------
# Inference — execute_query
# ---------------------------------------------------------------------------

def test_infer_prior_probability(src):
    result = src.execute_query(
        query={"target_node": "Weather", "target_state": "sunny", "context": {}},
        database="default", collection="weather",
    )
    assert len(result) == 1
    p = result[0]["probability"]
    assert abs(p - 0.7) < 0.01


def test_infer_with_evidence(src):
    result = src.execute_query(
        query={"target_node": "Umbrella", "target_state": "yes",
               "context": {"Weather": "rainy"}},
        database="default", collection="weather",
    )
    p = result[0]["probability"]
    assert p > 0.5   # rainy → likely umbrella


def test_infer_result_structure(src):
    result = src.execute_query(
        query={"target_node": "Umbrella", "target_state": "no", "context": {}},
        database="default", collection="weather",
    )[0]
    assert "probability" in result
    assert "probability_percent" in result
    assert "all_state_probabilities" in result
    assert set(result["all_state_probabilities"].keys()) == {"yes", "no"}


def test_infer_probabilities_sum_to_one(src):
    result = src.execute_query(
        query={"target_node": "Umbrella", "target_state": "yes", "context": {}},
        database="default", collection="weather",
    )[0]
    total = sum(result["all_state_probabilities"].values())
    assert abs(total - 1.0) < 1e-6


def test_infer_json_query_string(src):
    q = json.dumps({"target_node": "Weather", "target_state": "rainy", "context": {}})
    result = src.execute_query(query=q, database="default", collection="weather")
    assert result[0]["probability"] == pytest.approx(0.3, abs=0.01)


def test_infer_missing_collection_raises(src):
    with pytest.raises(Exception):
        src.execute_query(
            query={"target_node": "Weather", "target_state": "sunny", "context": {}},
            database="default", collection="nonexistent",
        )


def test_infer_missing_target_node_raises(src):
    with pytest.raises((ValueError, Exception)):
        src.execute_query(
            query={"target_node": "Ghost", "target_state": "sunny", "context": {}},
            database="default", collection="weather",
        )


def test_infer_missing_target_state_raises(src):
    with pytest.raises((ValueError, Exception)):
        src.execute_query(
            query={"target_node": "Weather", "target_state": "blizzard", "context": {}},
            database="default", collection="weather",
        )


def test_infer_no_collection_raises(src):
    with pytest.raises(Exception):
        src.execute_query(
            query={"target_node": "Weather", "target_state": "sunny"},
            database="default",
        )


def test_infer_no_target_node_raises(src):
    with pytest.raises(ValueError):
        src.execute_query(
            query={"target_state": "sunny", "context": {}},
            database="default", collection="weather",
        )


def test_infer_convenience_method(src):
    result = src.infer("weather", {"target_node": "Weather", "target_state": "sunny", "context": {}})
    assert "probability" in result


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

def test_explanation_text(src):
    result = src.execute_query(
        query={"target_node": "Umbrella", "target_state": "yes",
               "context": {"Weather": "rainy"}},
        database="default", collection="weather",
        optional_properties={"explanation": True},
    )[0]
    assert "explanation" in result
    assert isinstance(result["explanation"], str)
    assert len(result["explanation"]) > 0


def test_explanation_structured(src):
    result = src.execute_query(
        query={"target_node": "Umbrella", "target_state": "yes",
               "context": {"Weather": "rainy"}},
        database="default", collection="weather",
        optional_properties={"explanation": True, "structured_explanation": True},
    )[0]
    exp = result["explanation"]
    assert isinstance(exp, dict)
    assert "reasoning_paths" in exp
    assert exp["target_node"] == "Umbrella"


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def test_model_is_cached_after_first_load(src):
    src.execute_query(
        query={"target_node": "Weather", "target_state": "sunny", "context": {}},
        database="default", collection="weather",
    )
    assert "weather" in src._cache.get("default", {})


def test_cache_cleared_on_disconnect(src):
    src.execute_query(
        query={"target_node": "Weather", "target_state": "sunny", "context": {}},
        database="default", collection="weather",
    )
    src._disconnect()
    assert src._cache == {}
