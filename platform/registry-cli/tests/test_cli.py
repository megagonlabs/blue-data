from registry_cli.main import cli


# ---------------------------------------------------------------------------
# source list / add / remove
# ---------------------------------------------------------------------------

def test_source_list(runner):
    r = runner.invoke(cli, ["source", "list"])
    assert r.exit_code == 0
    assert "sales" in r.output


def test_source_list_json(runner):
    r = runner.invoke(cli, ["--json", "source", "list"])
    assert r.exit_code == 0
    import json
    names = json.loads(r.output)
    assert "sales" in names


def test_source_add_sqlite(runner, tmp_path):
    r = runner.invoke(cli, [
        "source", "add", "newdb",
        "--type", "sqlite",
        "--database-dir", str(tmp_path),
    ])
    assert r.exit_code == 0
    assert "newdb" in r.output


def test_source_add_and_remove(runner, tmp_path):
    runner.invoke(cli, ["source", "add", "tmp_src", "--type", "sqlite",
                        "--database-dir", str(tmp_path)])
    r = runner.invoke(cli, ["source", "remove", "tmp_src"])
    assert r.exit_code == 0
    assert "Removed" in r.output


def test_source_remove_not_found(runner):
    r = runner.invoke(cli, ["source", "remove", "ghost"])
    assert r.exit_code != 0
    assert "not found" in r.output


# ---------------------------------------------------------------------------
# source sync / stats / enrich / metadata
# ---------------------------------------------------------------------------

def test_source_sync(runner):
    r = runner.invoke(cli, ["source", "sync", "sales"])
    assert r.exit_code == 0
    assert "Synced" in r.output


def test_source_sync_unknown(runner):
    r = runner.invoke(cli, ["source", "sync", "ghost"])
    assert r.exit_code != 0


def test_source_stats(runner):
    r = runner.invoke(cli, ["source", "stats", "sales"])
    assert r.exit_code == 0
    assert "Stats collected" in r.output


def test_source_enrich(runner):
    r = runner.invoke(cli, ["source", "enrich", "sales"])
    assert r.exit_code == 0
    assert "Enriched" in r.output


def test_source_metadata(runner):
    r = runner.invoke(cli, ["source", "metadata", "sales"])
    assert r.exit_code == 0
    assert "complete" in r.output


def test_source_metadata_rebuild(runner):
    r = runner.invoke(cli, ["source", "metadata", "sales", "--rebuild"])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_returns_results(runner):
    r = runner.invoke(cli, ["search", "orders"])
    assert r.exit_code == 0
    assert "orders" in r.output


def test_search_json(runner):
    r = runner.invoke(cli, ["--json", "search", "orders"])
    assert r.exit_code == 0
    import json
    results = json.loads(r.output)
    assert isinstance(results, list)
    names = [rec["name"] for rec in results]
    assert "orders" in names


def test_search_type_filter(runner):
    r = runner.invoke(cli, ["--json", "search", "orders", "--type", "entity"])
    assert r.exit_code == 0
    import json
    results = json.loads(r.output)
    assert all(rec["type"] == "entity" for rec in results)


# ---------------------------------------------------------------------------
# source inspect
# ---------------------------------------------------------------------------

def test_inspect_source(runner):
    r = runner.invoke(cli, ["source", "inspect", "sales"])
    assert r.exit_code == 0
    assert "sales" in r.output


def test_inspect_source_not_found(runner):
    r = runner.invoke(cli, ["source", "inspect", "ghost"])
    assert r.exit_code != 0


def test_inspect_database(runner):
    r = runner.invoke(cli, ["source", "inspect", "sales", "prod"])
    assert r.exit_code == 0
    assert "prod" in r.output
    assert "public" in r.output


def test_inspect_collection(runner):
    r = runner.invoke(cli, ["source", "inspect", "sales", "prod", "public"])
    assert r.exit_code == 0
    assert "orders" in r.output
    assert "customers" in r.output


def test_inspect_entity(runner):
    r = runner.invoke(cli, ["source", "inspect", "sales", "prod", "public", "orders"])
    assert r.exit_code == 0
    assert "total" in r.output
    assert "status" in r.output


def test_inspect_attribute(runner):
    r = runner.invoke(cli, ["source", "inspect", "sales", "prod", "public", "orders", "total"])
    assert r.exit_code == 0
    assert "total" in r.output


def test_inspect_json(runner):
    r = runner.invoke(cli, ["--json", "source", "inspect", "sales", "prod", "public", "orders"])
    assert r.exit_code == 0
    import json
    data = json.loads(r.output)
    assert data["record"]["name"] == "orders"


# ---------------------------------------------------------------------------
# source query
# ---------------------------------------------------------------------------

def test_query(runner):
    r = runner.invoke(cli, ["source", "query", "sales", "SELECT * FROM orders", "--database", "prod"])
    assert r.exit_code == 0


def test_query_invalid(runner):
    r = runner.invoke(cli, ["source", "query", "sales", "SELECT * FROM nope", "--database", "prod"])
    assert r.exit_code != 0
