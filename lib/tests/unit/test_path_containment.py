"""#117 (XR-09) — a caller-supplied `database` name must not escape the configured
directory. Covers the `contain` helper and its use in SQLiteDBSource and FileGraphSource
(the latter inherited by kb-source's FileKBSource)."""
import os
import sqlite3

import pytest

from blue_data.core.utils.path_utils import contain
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.graph.file_graph_source import FileGraphSource


# ---------- contain() ----------

def test_contain_allows_single_component(tmp_path):
    p = contain(str(tmp_path), "shop", ".db")
    assert p == str((tmp_path / "shop.db").resolve())


@pytest.mark.parametrize("name", [
    "../outside/other",   # parent traversal
    "..",                 # bare parent
    ".",                  # bare self
    "a/b",                # nested separator
    "",                   # empty
    "/etc/passwd",        # absolute
])
def test_contain_rejects_unsafe_names(tmp_path, name):
    with pytest.raises(ValueError):
        contain(str(tmp_path), name, ".json")


def test_contain_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir()
    root = tmp_path / "root"; root.mkdir()
    (outside / "secret.json").write_text("{}")
    # a symlink inside root pointing outside resolves out -> refused
    os.symlink(outside / "secret.json", root / "link.json")
    with pytest.raises(ValueError):
        contain(str(root), "link", ".json")


# ---------- SQLiteDBSource (BD-08) ----------

def test_sqlite_refuses_traversal(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    c = sqlite3.connect(outside / "other.db")
    c.execute("create table t(v text)"); c.execute("insert into t values('x')"); c.commit(); c.close()

    src = SQLiteDBSource(name="s", properties={"connection": {"database_directory": str(root)}})
    with pytest.raises(ValueError):
        src.execute_query("select v from t", database="../outside/other")


def test_sqlite_normal_name_works(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    c = sqlite3.connect(root / "shop.db")
    c.execute("create table o(x int)"); c.execute("insert into o values(1)"); c.commit(); c.close()

    src = SQLiteDBSource(name="s", properties={"connection": {"database_directory": str(root)}})
    assert src.execute_query("select x from o", database="shop") == [{"x": 1}]


# ---------- FileGraphSource (KBS-01 root cause) ----------

def test_file_graph_refuses_traversal(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()

    kb = FileGraphSource("k", directory=str(root))
    with pytest.raises(ValueError):
        kb._db_path("../outside/kb")
    assert sorted(os.listdir(outside)) == []


def test_file_graph_normal_name_works(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    kb = FileGraphSource("k", directory=str(root))
    kb.create_database("mykb")
    kb._nodes["mykb"] = {}; kb._edges["mykb"] = {}
    kb._save("mykb")
    assert (root / "mykb.json").exists()


def test_file_graph_txn_path_contained(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    kb = FileGraphSource("k", directory=str(root))
    assert kb._txn_path("mykb", "abc123").startswith(str(root.resolve()))
    with pytest.raises(ValueError):
        kb._txn_path("../outside/kb", "abc123")
