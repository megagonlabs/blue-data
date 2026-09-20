def test_list_sources(client):
    r = client.get("/sources")
    assert r.status_code == 200
    assert "sales" in r.json()["results"]


def test_get_source(client):
    r = client.get("/sales")
    assert r.status_code == 200
    assert r.json()["result"]["name"] == "sales"


def test_get_source_not_found(client):
    r = client.get("/nonexistent")
    assert r.status_code == 404


def test_list_databases(client):
    r = client.get("/sales/databases")
    assert r.status_code == 200
    names = [db["name"] for db in r.json()["results"]]
    assert "prod" in names


def test_get_source_properties(client):
    r = client.get("/sales/properties")
    assert r.status_code == 200
    assert "results" in r.json()


def test_get_source_property(client):
    r = client.get("/sales/property/connection")
    assert r.status_code == 200


def test_sync_source(client):
    r = client.put("/sales/sync")
    assert r.status_code == 200
    assert r.json()["message"] == "Success"


def test_sync_source_not_found(client):
    r = client.put("/ghost/sync")
    assert r.status_code == 404


def test_collect_stats(client):
    r = client.put("/sales/stats")
    assert r.status_code == 200


def test_enrich_source(client):
    r = client.put("/sales/enrich")
    assert r.status_code == 200


def test_enrich_source_metadata(client):
    r = client.put("/sales/metadata")
    assert r.status_code == 200


def test_enrich_source_metadata_rebuild(client):
    r = client.put("/sales/metadata", params={"rebuild": True})
    assert r.status_code == 200


def test_connect_source(client):
    r = client.post("/sales/connect")
    assert r.status_code == 200
    result = r.json()["result"]
    assert "type" in result
    assert "source_tree" in result


def test_execute_query(client):
    r = client.post(
        "/sales/query",
        json={"query": "SELECT * FROM orders", "database": "prod"},
    )
    assert r.status_code == 200
    assert isinstance(r.json()["results"], list)


def test_execute_query_invalid(client):
    r = client.post(
        "/sales/query",
        json={"query": "SELECT * FROM nonexistent_table_xyz", "database": "prod"},
    )
    assert r.status_code == 500


def test_delete_source(client):
    r = client.delete("/sales")
    assert r.status_code == 200
    # confirm it's gone
    assert client.get("/sales").status_code == 404
