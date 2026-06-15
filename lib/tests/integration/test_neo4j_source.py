"""Integration tests for NEO4JSource.

Requires a running Neo4j instance. Auto-skipped when unavailable.

Default connection: bolt://localhost:7687, user=neo4j, password=neo4j.
Override via: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.

Each test that writes data works on a uniquely named database so tests
are isolated and teardown is a simple DROP DATABASE.

Run just these tests:
    python3 -m pytest lib/tests/integration/test_neo4j_source.py -v
"""
import os
import uuid

import pytest

try:
    from neo4j import GraphDatabase as _GDB
except ImportError:
    _GDB = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _neo4j_uri():
    return os.environ.get("NEO4J_URI", "bolt://localhost:7687")

def _neo4j_auth():
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw   = os.environ.get("NEO4J_PASSWORD", "neo4j")
    return user, pw


def _neo4j_available():
    if _GDB is None:
        return False
    try:
        driver = _GDB.driver(_neo4j_uri(), auth=_neo4j_auth())
        with driver.session() as s:
            s.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


skip_no_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j not available — set NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD or start a local instance",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def src():
    from source.graph.neo4j.neo4j_graph_source import NEO4JSource
    user, pw = _neo4j_auth()
    source = NEO4JSource(
        name="test_neo4j",
        properties={"connection": {
            "host":     _neo4j_uri().split("://")[-1].split(":")[0],
            "port":     int(_neo4j_uri().split(":")[-1]) if ":" in _neo4j_uri().split("://")[-1] else 7687,
            "protocol": _neo4j_uri().split("://")[0],
            "user":     user,
            "password": pw,
        }},
    )
    yield source
    source._disconnect()


@pytest.fixture
def testdb(src):
    """Create a unique database and drop it after each test."""
    db_name = f"bdtest{uuid.uuid4().hex[:10]}"
    src.create_database(db_name)
    yield db_name
    try:
        src._run_query(f"DROP DATABASE `{db_name}` IF EXISTS", read=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Source-level
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_fetch_databases_includes_neo4j(src):
    dbs = src.fetch_databases()
    assert isinstance(dbs, list)
    assert len(dbs) >= 1


@skip_no_neo4j
def test_fetch_source_stats(src):
    stats = src.fetch_source_stats()
    assert "database_count" in stats
    assert stats["database_count"] >= 1


@skip_no_neo4j
def test_fetch_metadata(src):
    meta = src.fetch_metadata()
    assert "source_type" in meta
    assert meta["source_type"] == "neo4j"
    assert "neo4j_version" in meta


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_create_database(src, testdb):
    assert testdb in src.fetch_databases()


@skip_no_neo4j
def test_create_database_skips_when_exists(src, testdb):
    result = src.create_database(testdb, overwrite=False)
    assert result["status"] == "skipped"


@skip_no_neo4j
def test_create_database_overwrite(src, testdb):
    result = src.create_database(testdb, overwrite=True)
    assert result["status"] == "success"


@skip_no_neo4j
def test_fetch_database_metadata(src, testdb):
    meta = src.fetch_database_metadata(testdb)
    assert "node_count" in meta
    assert "relationship_count" in meta


@skip_no_neo4j
def test_fetch_database_stats(src, testdb):
    stats = src.fetch_database_stats(testdb)
    assert "node_count" in stats
    assert "relationship_count" in stats


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_fetch_database_collections_returns_database_name(src, testdb):
    cols = src.fetch_database_collections(testdb)
    assert cols == [testdb]


@skip_no_neo4j
def test_create_database_collection_returns_registry_only(src, testdb):
    result = src.create_database_collection(testdb, testdb)
    assert result["status"] == "registry_only"


# ---------------------------------------------------------------------------
# Entities / nodes
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_nodes(src, testdb):
    """Populate testdb with Person and Movie nodes."""
    src.create_database_collection_entity(
        testdb, testdb, "Person",
        properties={"sample_properties": {"name": "Alice", "age": 30}},
    )
    src.create_database_collection_entity(
        testdb, testdb, "Movie",
        properties={"sample_properties": {"title": "Inception", "year": 2010}},
    )
    src._schema_cache.clear()
    return testdb


@skip_no_neo4j
def test_create_entity_success(src, testdb):
    result = src.create_database_collection_entity(
        testdb, testdb, "Person",
        properties={"sample_properties": {"name": "Bob"}},
    )
    assert result["status"] == "success"


@skip_no_neo4j
def test_fetch_entities_returns_node_labels(src, db_with_nodes):
    entities = src.fetch_database_collection_entities(db_with_nodes, db_with_nodes)
    assert "Person" in entities
    assert "Movie" in entities


@skip_no_neo4j
def test_fetch_entities_includes_properties(src, db_with_nodes):
    entities = src.fetch_database_collection_entities(db_with_nodes, db_with_nodes)
    attrs = entities["Person"]["contents"]["attributes"]
    assert "name" in attrs
    assert "age" in attrs


@skip_no_neo4j
def test_create_entity_overwrite_clears_nodes(src, testdb):
    src.create_database_collection_entity(
        testdb, testdb, "TempNode",
        properties={"sample_properties": {"x": 1}},
    )
    src.create_database_collection_entity(
        testdb, testdb, "TempNode",
        properties={"sample_properties": {"x": 2}},
        overwrite=True,
    )
    stats = src.fetch_entity_stats(testdb, testdb, "TempNode")
    assert stats["row_count"] == 1


# ---------------------------------------------------------------------------
# Entity stats
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_fetch_entity_stats_row_count(src, db_with_nodes):
    stats = src.fetch_entity_stats(db_with_nodes, db_with_nodes, "Person")
    assert stats["row_count"] >= 1
    assert stats["node_count"] == stats["row_count"]


@skip_no_neo4j
def test_fetch_entity_stats_zero_for_missing_label(src, testdb):
    stats = src.fetch_entity_stats(testdb, testdb, "Ghost")
    assert stats["row_count"] == 0


# ---------------------------------------------------------------------------
# Property stats
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_fetch_property_stats(src, db_with_nodes):
    stats = src.fetch_property_stats(db_with_nodes, db_with_nodes, "Person", "name")
    assert stats["count"] >= 1
    assert stats["distinct_count"] >= 1
    assert len(stats["sample_values"]) >= 1


@skip_no_neo4j
def test_fetch_property_stats_most_common_vals(src, db_with_nodes):
    stats = src.fetch_property_stats(db_with_nodes, db_with_nodes, "Person", "name")
    assert isinstance(stats["most_common_vals"], list)


# ---------------------------------------------------------------------------
# execute_query
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_execute_query_read(src, db_with_nodes):
    result = src.execute_query(
        "MATCH (n:Person) RETURN count(n) AS cnt",
        database=db_with_nodes,
    )
    assert result[0]["cnt"] >= 1


@skip_no_neo4j
def test_execute_query_write(src, testdb):
    src.execute_query(
        "CREATE (n:Widget {id: 1})",
        database=testdb,
        optional_properties={"read": False},
    )
    result = src.execute_query(
        "MATCH (n:Widget) RETURN count(n) AS cnt",
        database=testdb,
    )
    assert result[0]["cnt"] == 1


# ---------------------------------------------------------------------------
# Schema caching
# ---------------------------------------------------------------------------

@skip_no_neo4j
def test_schema_cached_after_first_call(src, db_with_nodes):
    src._schema_cache.clear()
    src.fetch_database_collection_entities(db_with_nodes, db_with_nodes)
    assert (db_with_nodes, db_with_nodes) in src._schema_cache


@skip_no_neo4j
def test_create_entity_clears_schema_cache(src, db_with_nodes):
    src.fetch_database_collection_entities(db_with_nodes, db_with_nodes)
    src.create_database_collection_entity(
        db_with_nodes, db_with_nodes, "NewLabel",
        properties={"sample_properties": {"x": 1}},
    )
    assert (db_with_nodes, db_with_nodes) not in src._schema_cache
