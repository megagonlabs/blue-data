"""Unit tests for GraphSource transaction support on MemoryGraphSource and FileGraphSource."""
import pytest

from blue_data.source.graph.memory_graph_source import MemoryGraphSource
from blue_data.source.graph.file_graph_source import FileGraphSource

DB = "social"


def _sources(tmp_path):
    return [
        MemoryGraphSource("mem"),
        FileGraphSource("file", directory=str(tmp_path)),
    ]


def _make(tmp_path, kind):
    if kind == "mem":
        return MemoryGraphSource("mem")
    return FileGraphSource("file", directory=str(tmp_path))


@pytest.fixture(params=["mem", "file"])
def graph(request, tmp_path):
    g = _make(tmp_path, request.param)
    g.create_database(DB)
    return g


# ===========================================================================
# Isolation: transaction_id gates visibility
# ===========================================================================

def test_write_in_transaction_invisible_without_transaction_id(graph):
    txn_id = graph.begin_transaction(DB)
    node_id = graph.add_node(DB, "Person", {"name": "Alice"}, transaction_id=txn_id)

    assert graph.get_node(DB, node_id) is None
    assert graph.get_node(DB, node_id, transaction_id=txn_id) is not None


def test_committed_state_untouched_until_commit(graph):
    graph.add_node(DB, "Person", node_id="pre-existing")
    txn_id = graph.begin_transaction(DB)
    graph.delete_node(DB, "pre-existing", transaction_id=txn_id)

    assert graph.get_node(DB, "pre-existing") is not None
    assert graph.get_node(DB, "pre-existing", transaction_id=txn_id) is None


def test_transaction_starts_from_committed_snapshot(graph):
    graph.add_node(DB, "Person", node_id="base")
    txn_id = graph.begin_transaction(DB)
    assert graph.get_node(DB, "base", transaction_id=txn_id) is not None


# ===========================================================================
# commit / rollback
# ===========================================================================

def test_commit_applies_changes(graph):
    txn_id = graph.begin_transaction(DB)
    node_id = graph.add_node(DB, "Person", {"name": "Bob"}, transaction_id=txn_id)
    graph.commit_transaction(txn_id)

    node = graph.get_node(DB, node_id)
    assert node is not None
    assert node["properties"]["name"] == "Bob"


def test_rollback_discards_changes(graph):
    graph.add_node(DB, "Person", node_id="keep")
    txn_id = graph.begin_transaction(DB)
    graph.add_node(DB, "Person", node_id="scratch", transaction_id=txn_id)
    graph.delete_node(DB, "keep", transaction_id=txn_id)
    graph.rollback_transaction(txn_id)

    assert graph.get_node(DB, "keep") is not None
    assert graph.get_node(DB, "scratch") is None


def test_operations_after_commit_or_rollback_are_gone(graph):
    txn_id = graph.begin_transaction(DB)
    graph.add_node(DB, "Person", transaction_id=txn_id)
    graph.commit_transaction(txn_id)
    with pytest.raises(KeyError):
        graph.get_node(DB, "x", transaction_id=txn_id)


# ===========================================================================
# operation log
# ===========================================================================

def test_get_transaction_operations_records_mutations(graph):
    txn_id = graph.begin_transaction(DB)
    node_id = graph.add_node(DB, "Person", {"name": "Carol"}, transaction_id=txn_id)
    graph.update_node(DB, node_id, {"age": 40}, transaction_id=txn_id)

    ops = graph.get_transaction_operations(txn_id)
    op_names = [op["op"] for op in ops]
    assert op_names == ["add_node", "update_node"]


def test_reads_do_not_get_logged(graph):
    txn_id = graph.begin_transaction(DB)
    node_id = graph.add_node(DB, "Person", transaction_id=txn_id)
    graph.get_node(DB, node_id, transaction_id=txn_id)
    graph.match_nodes(DB, transaction_id=txn_id)

    ops = graph.get_transaction_operations(txn_id)
    assert len(ops) == 1
    assert ops[0]["op"] == "add_node"


# ===========================================================================
# list_transactions
# ===========================================================================

def test_list_transactions(graph):
    txn_id = graph.begin_transaction(DB)
    assert txn_id in graph.list_transactions()
    assert txn_id in graph.list_transactions(database=DB)
    assert txn_id not in graph.list_transactions(database="other_db")

    graph.commit_transaction(txn_id)
    assert txn_id not in graph.list_transactions()


# ===========================================================================
# transaction() context manager
# ===========================================================================

def test_context_manager_commits_on_success(graph):
    with graph.transaction(DB) as txn_id:
        node_id = graph.add_node(DB, "Person", transaction_id=txn_id)

    assert graph.get_node(DB, node_id) is not None


def test_context_manager_rolls_back_on_exception(graph):
    with pytest.raises(RuntimeError):
        with graph.transaction(DB) as txn_id:
            graph.add_node(DB, "Person", node_id="doomed", transaction_id=txn_id)
            raise RuntimeError("boom")

    assert graph.get_node(DB, "doomed") is None
    assert graph.list_transactions(database=DB) == []


# ===========================================================================
# mismatched database
# ===========================================================================

def test_transaction_id_for_wrong_database_raises(graph):
    graph.create_database("other_db")
    txn_id = graph.begin_transaction(DB)
    with pytest.raises(ValueError):
        graph.get_node("other_db", "x", transaction_id=txn_id)


# ===========================================================================
# FileGraphSource-specific: sidecar persistence / cross-instance resume
# ===========================================================================

def test_file_backend_transaction_resumable_from_fresh_instance(tmp_path):
    writer = FileGraphSource("writer", directory=str(tmp_path))
    writer.create_database(DB)
    txn_id = writer.begin_transaction(DB)
    node_id = writer.add_node(DB, "Person", {"name": "Dana"}, transaction_id=txn_id)

    # A brand new instance pointed at the same directory never called begin_transaction itself.
    reader = FileGraphSource("reader", directory=str(tmp_path))
    assert txn_id in reader.list_transactions(database=DB)
    assert reader.get_node(DB, node_id, transaction_id=txn_id)["properties"]["name"] == "Dana"
    ops = reader.get_transaction_operations(txn_id)
    assert ops[0]["op"] == "add_node"

    # committing from the fresh instance persists to the real database file.
    reader.commit_transaction(txn_id)
    assert writer.get_node(DB, node_id) is not None
    assert reader.list_transactions(database=DB) == []


def test_file_backend_list_transactions_does_not_instantiate(tmp_path, monkeypatch):
    src = FileGraphSource("file", directory=str(tmp_path))
    src.create_database(DB)
    txn_id = src.begin_transaction(DB)
    src.add_node(DB, "Person", transaction_id=txn_id)

    fresh = FileGraphSource("fresh", directory=str(tmp_path))

    def _boom(*args, **kwargs):
        raise AssertionError("list_transactions must not hydrate GraphTransaction objects")

    monkeypatch.setattr(fresh, "_hydrate_transaction", _boom)
    assert fresh.list_transactions(database=DB) == [txn_id]


def test_file_backend_rollback_leaves_committed_file_untouched(tmp_path):
    src = FileGraphSource("file", directory=str(tmp_path))
    src.create_database(DB)
    src.add_node(DB, "Person", node_id="keep")

    txn_id = src.begin_transaction(DB)
    src.add_node(DB, "Person", node_id="scratch", transaction_id=txn_id)

    import json
    with open(src._db_path(DB)) as f:
        before = json.load(f)

    src.rollback_transaction(txn_id)

    with open(src._db_path(DB)) as f:
        after = json.load(f)
    assert before == after
    assert "scratch" not in after["nodes"]


# ===========================================================================
# execute_query wiring
# ===========================================================================

def test_execute_query_honors_transaction_id(tmp_path):
    for src in _sources(tmp_path):
        src.create_database(DB)
        txn_id = src.begin_transaction(DB)
        node_id = src.execute_query(
            {"op": "GRAPH.ADD_NODE", "label": "Person", "transaction_id": txn_id},
            database=DB,
        )
        assert src.execute_query({"op": "GRAPH.GET_NODE", "node_id": node_id}, database=DB) is None
        assert src.execute_query(
            {"op": "GRAPH.GET_NODE", "node_id": node_id, "transaction_id": txn_id}, database=DB
        ) is not None

        assert src.get_transaction_operations(txn_id)[0]["op"] == "add_node"

        src.commit_transaction(txn_id)
        assert src.execute_query({"op": "GRAPH.GET_NODE", "node_id": node_id}, database=DB) is not None
        assert src.list_transactions(database=DB) == []


def test_execute_query_does_not_expose_transaction_lifecycle(tmp_path):
    for src in _sources(tmp_path):
        src.create_database(DB)
        with pytest.raises(ValueError, match="Unsupported"):
            src.execute_query({"op": "GRAPH.BEGIN_TRANSACTION"}, database=DB)
