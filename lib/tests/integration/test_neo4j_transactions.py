"""Integration tests for NEO4JSource transaction support.

Requires a running Neo4j instance. Auto-skipped when unavailable.

Default connection: bolt://localhost:7687, user=neo4j, password=neo4j.
Override via: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.

Neo4j Community Edition doesn't support multiple databases, so all tests
target the default database and clean up by deleting the nodes they create
(matched by a unique test label) rather than relying on database isolation.

Run just these tests:
    python3 -m pytest lib/tests/integration/test_neo4j_transactions.py -v
"""
import os
import uuid

import pytest

try:
    from neo4j import GraphDatabase as _GDB
except ImportError:
    _GDB = None


DB = "neo4j"
LABEL = "TxnSmokeTest"


def _neo4j_uri():
    return os.environ.get("NEO4J_URI", "bolt://localhost:7687")

def _neo4j_auth():
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ.get("NEO4J_PASSWORD", "neo4j")
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


@pytest.fixture(scope="module")
def src():
    from blue_data.source.graph.neo4j.neo4j_graph_source import NEO4JSource
    user, pw = _neo4j_auth()
    source = NEO4JSource(
        name="test_neo4j_txn",
        properties={"connection": {
            "host": _neo4j_uri().split("://")[-1].split(":")[0],
            "port": int(_neo4j_uri().split(":")[-1]) if ":" in _neo4j_uri().split("://")[-1] else 7687,
            "protocol": _neo4j_uri().split("://")[0],
            "user": user,
            "password": pw,
        }},
    )
    yield source
    source._disconnect()


@pytest.fixture(autouse=True)
def _cleanup(src):
    """Delete any leftover TxnSmokeTest nodes before and after each test."""
    def _wipe():
        src.execute_query(f"MATCH (n:`{LABEL}`) DETACH DELETE n", database=DB, optional_properties={"read": False})
    _wipe()
    yield
    _wipe()


@skip_no_neo4j
def test_write_in_transaction_invisible_until_commit(src):
    txn_id = src.begin_transaction(DB)
    node_id = src.add_node(DB, LABEL, {"name": "Alice"}, node_id=str(uuid.uuid4()), transaction_id=txn_id)

    assert src.get_node(DB, node_id) is None
    seen = src.get_node(DB, node_id, transaction_id=txn_id)
    assert seen is not None
    assert seen["properties"]["name"] == "Alice"

    src.commit_transaction(txn_id)
    assert src.get_node(DB, node_id) is not None


@skip_no_neo4j
def test_rollback_discards_changes(src):
    txn_id = src.begin_transaction(DB)
    node_id = src.add_node(DB, LABEL, node_id=str(uuid.uuid4()), transaction_id=txn_id)
    src.rollback_transaction(txn_id)

    assert src.get_node(DB, node_id) is None
    with pytest.raises(KeyError):
        src.get_node(DB, node_id, transaction_id=txn_id)


@skip_no_neo4j
def test_transaction_operations_are_logged(src):
    txn_id = src.begin_transaction(DB)
    node_id = src.add_node(DB, LABEL, {"name": "Bob"}, node_id=str(uuid.uuid4()), transaction_id=txn_id)
    src.update_node(DB, node_id, {"age": 42}, transaction_id=txn_id)

    ops = src.get_transaction_operations(txn_id)
    assert [op["op"] for op in ops] == ["add_node", "update_node"]

    src.rollback_transaction(txn_id)


@skip_no_neo4j
def test_list_transactions(src):
    txn_id = src.begin_transaction(DB)
    assert txn_id in src.list_transactions(database=DB)
    src.rollback_transaction(txn_id)
    assert txn_id not in src.list_transactions(database=DB)


@skip_no_neo4j
def test_context_manager_commits_on_success(src):
    with src.transaction(DB) as txn_id:
        node_id = src.add_node(DB, LABEL, node_id=str(uuid.uuid4()), transaction_id=txn_id)

    assert src.get_node(DB, node_id) is not None


@skip_no_neo4j
def test_context_manager_rolls_back_on_exception(src):
    with pytest.raises(RuntimeError):
        with src.transaction(DB) as txn_id:
            node_id = src.add_node(DB, LABEL, node_id=str(uuid.uuid4()), transaction_id=txn_id)
            raise RuntimeError("boom")

    assert src.get_node(DB, node_id) is None
