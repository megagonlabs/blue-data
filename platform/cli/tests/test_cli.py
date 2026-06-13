from registry_cli.main import cli


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

def test_sources_list(runner):
    r = runner.invoke(cli, ["sources", "list"])
    assert r.exit_code == 0
    assert "sales" in r.output


def test_sources_list_json(runner):
    r = runner.invoke(cli, ["--json", "sources", "list"])
    assert r.exit_code == 0
    import json
    names = json.loads(r.output)
    assert "sales" in names


def test_sources_add_sqlite(runner, tmp_path):
    r = runner.invoke(cli, [
        "sources", "add", "newdb",
        "--type", "sqlite",
        "--database-dir", str(tmp_path),
    ])
    assert r.exit_code == 0
    assert "newdb" in r.output


def test_sources_add_and_remove(runner, tmp_path):
    runner.invoke(cli, ["sources", "add", "tmp_src", "--type", "sqlite",
                        "--database-dir", str(tmp_path)])
    r = runner.invoke(cli, ["sources", "remove", "tmp_src"])
    assert r.exit_code == 0
    assert "Removed" in r.output


def test_sources_remove_not_found(runner):
    r = runner.invoke(cli, ["sources", "remove", "ghost"])
    assert r.exit_code != 0
    assert "not found" in r.output


# ---------------------------------------------------------------------------
# sync / stats / enrich / metadata
# ---------------------------------------------------------------------------

def test_sync(runner):
    r = runner.invoke(cli, ["sync", "sales"])
    assert r.exit_code == 0
    assert "Synced" in r.output


def test_sync_unknown_source(runner):
    r = runner.invoke(cli, ["sync", "ghost"])
    assert r.exit_code != 0


def test_stats(runner):
    r = runner.invoke(cli, ["stats", "sales"])
    assert r.exit_code == 0
    assert "Stats collected" in r.output


def test_enrich(runner):
    r = runner.invoke(cli, ["enrich", "sales"])
    assert r.exit_code == 0
    assert "Enriched" in r.output


def test_metadata(runner):
    r = runner.invoke(cli, ["metadata", "sales"])
    assert r.exit_code == 0
    assert "complete" in r.output


def test_metadata_rebuild(runner):
    r = runner.invoke(cli, ["metadata", "sales", "--rebuild"])
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
# inspect
# ---------------------------------------------------------------------------

def test_inspect_source(runner):
    r = runner.invoke(cli, ["inspect", "source", "sales"])
    assert r.exit_code == 0
    assert "sales" in r.output


def test_inspect_source_not_found(runner):
    r = runner.invoke(cli, ["inspect", "source", "ghost"])
    assert r.exit_code != 0


def test_inspect_database(runner):
    r = runner.invoke(cli, ["inspect", "database", "sales", "prod"])
    assert r.exit_code == 0
    assert "prod" in r.output
    assert "public" in r.output


def test_inspect_collection(runner):
    r = runner.invoke(cli, ["inspect", "collection", "sales", "prod", "public"])
    assert r.exit_code == 0
    assert "orders" in r.output
    assert "customers" in r.output


def test_inspect_entity(runner):
    r = runner.invoke(cli, ["inspect", "entity", "sales", "prod", "public", "orders"])
    assert r.exit_code == 0
    assert "total" in r.output
    assert "status" in r.output


def test_inspect_attribute(runner):
    r = runner.invoke(cli, ["inspect", "attribute", "sales", "prod", "public", "orders", "total"])
    assert r.exit_code == 0
    assert "total" in r.output


def test_inspect_json(runner):
    r = runner.invoke(cli, ["--json", "inspect", "entity", "sales", "prod", "public", "orders"])
    assert r.exit_code == 0
    import json
    data = json.loads(r.output)
    assert data["record"]["name"] == "orders"


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def test_query(runner):
    r = runner.invoke(cli, ["query", "sales", "SELECT * FROM orders", "--database", "prod"])
    assert r.exit_code == 0


def test_query_invalid(runner):
    r = runner.invoke(cli, ["query", "sales", "SELECT * FROM nope", "--database", "prod"])
    assert r.exit_code != 0
