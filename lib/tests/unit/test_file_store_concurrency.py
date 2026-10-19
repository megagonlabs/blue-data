"""Concurrent writers on FileJSONSource and FileGraphSource (#124).

Two writer processes on one store, like a CLI and an MCP server sharing a data
directory, must not lose each other's updates or leave an unreadable file, and
a concurrent reader must never see a partial file.
"""
import json
import multiprocessing as mp
import os

import pytest

from blue_data.core.utils.file_lock import file_lock, write_json_atomic
from blue_data.source.graph.file_graph_source import FileGraphSource
from blue_data.source.json.file_json_source import FileJSONSource

N = 50
DB = "main"
TIMEOUT = 60

_ctx = mp.get_context("fork")


def _child(worker, start, stop, results, *args):
    """Run *worker* once *start* is set and report its error list; a crash counts as an error."""
    try:
        start.wait()
        errors = worker(stop, *args)
    except BaseException as e:
        errors = [f"worker crashed: {e!r}"]
    results.put(errors)


def _run(writers, reader=None):
    """Start (worker, args) writers, plus an optional reader that loops until they finish.

    Returns every process's error list, writers first.
    """
    start, stop, results = _ctx.Event(), _ctx.Event(), _ctx.Queue()
    specs = list(writers) + ([reader] if reader else [])
    procs = [
        _ctx.Process(target=_child, args=(w, start, stop, results, *args), daemon=True)
        for w, args in specs
    ]
    for p in procs:
        p.start()
    start.set()
    try:
        errors = [results.get(timeout=TIMEOUT) for _ in writers]
        stop.set()
        if reader:
            errors.append(results.get(timeout=TIMEOUT))
    finally:
        stop.set()
        for p in procs:
            p.join(timeout=TIMEOUT)
            if p.is_alive():
                p.terminate()
    return errors


def _json_writer(stop, path, tag):
    s = FileJSONSource(properties={"connection": {"path": path}})
    errors = []
    for i in range(N):
        try:
            s.set(f"{tag}_{i}", i)
        except Exception as e:
            errors.append(repr(e))
    return errors


def _json_reader(stop, path):
    s = FileJSONSource(properties={"connection": {"path": path}})
    errors = []
    while not stop.is_set():
        try:
            s.get()
        except Exception as e:
            errors.append(repr(e))
    return errors[:5]


def _graph_writer(stop, directory, tag):
    g = FileGraphSource("g", directory=directory)
    errors = []
    for i in range(N):
        try:
            g.add_node(DB, "Thing", {"tag": tag}, node_id=f"{tag}_{i}")
        except Exception as e:
            errors.append(repr(e))
    return errors


def _graph_reader(stop, directory):
    g = FileGraphSource("g", directory=directory)
    errors = []
    while not stop.is_set():
        try:
            g.match_nodes(DB)
        except Exception as e:
            errors.append(repr(e))
    return errors[:5]


def _graph_txn_writer(stop, directory, tag):
    g = FileGraphSource("g", directory=directory)
    errors = []
    for i in range(N // 5):
        try:
            g.add_node(DB, "Plain", node_id=f"{tag}_plain_{i}")
            txn = g.begin_transaction(DB)
            g.add_node(DB, "Txn", node_id=f"{tag}_txn_{i}", transaction_id=txn)
            g.commit_transaction(txn)
        except Exception as e:
            errors.append(repr(e))
    return errors


def test_two_processes_on_one_json_file_keep_every_key(tmp_path):
    path = str(tmp_path / "store.json")
    errors = _run(
        [(_json_writer, (path, "a")), (_json_writer, (path, "b"))], reader=(_json_reader, (path,))
    )
    assert errors == [[], [], []]
    with open(path) as f:
        data = json.load(f)
    assert set(data) == {f"{t}_{i}" for t in "ab" for i in range(N)}
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_two_processes_on_one_graph_database_keep_every_node(tmp_path):
    directory = str(tmp_path)
    FileGraphSource("g", directory=directory).create_database(DB)
    errors = _run(
        [(_graph_writer, (directory, "A")), (_graph_writer, (directory, "B"))],
        reader=(_graph_reader, (directory,)),
    )
    assert errors == [[], [], []]
    with open(tmp_path / f"{DB}.json") as f:
        nodes = json.load(f)["nodes"]
    assert set(nodes) == {f"{t}_{i}" for t in "AB" for i in range(N)}
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_concurrent_commits_and_writes_stay_readable(tmp_path):
    """commit_transaction holds the lock, so no writer ever sees a partial file.

    A commit replaces the database with the transaction's snapshot, so plain
    writes made between begin and commit may be overwritten; that is the
    transaction model, not this test's concern. No writer may raise,
    the file must stay readable and the last commit must be on disk.
    """
    directory = str(tmp_path)
    FileGraphSource("g", directory=directory).create_database(DB)
    errors = _run([(_graph_txn_writer, (directory, "A")), (_graph_txn_writer, (directory, "B"))])
    assert errors == [[], []]
    with open(tmp_path / f"{DB}.json") as f:
        nodes = json.load(f)["nodes"]
    last = N // 5 - 1
    # Whichever commit ran last must be in the file.
    assert f"A_txn_{last}" in nodes or f"B_txn_{last}" in nodes
    assert FileGraphSource("g", directory=directory).list_transactions(DB) == []


# ---------- helpers ----------

def test_file_lock_is_reentrant(tmp_path):
    path = tmp_path / "x.json"
    with file_lock(path):
        with file_lock(str(path)):
            pass
    with file_lock(path):
        pass


def test_failed_atomic_write_leaves_file_intact(tmp_path):
    path = tmp_path / "x.json"
    write_json_atomic(path, {"ok": 1})
    with pytest.raises(TypeError):
        write_json_atomic(path, {"bad": object()})
    assert json.loads(path.read_text()) == {"ok": 1}
    assert os.listdir(tmp_path) == ["x.json"]


def test_atomic_write_keeps_existing_mode(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{}")
    os.chmod(path, 0o640)
    write_json_atomic(path, {"a": 1})
    assert os.stat(path).st_mode & 0o777 == 0o640


def test_json_source_file_mode_is_0600(tmp_path):
    path = tmp_path / "store.json"
    s = FileJSONSource(properties={"connection": {"path": str(path)}})
    s.set("k", "v")
    assert os.stat(path).st_mode & 0o777 == 0o600
