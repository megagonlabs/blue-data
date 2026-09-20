def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_records_all(client):
    r = client.get("/")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0


def test_list_records_type_filter(client):
    r = client.get("/", params={"type": "entity"})
    assert r.status_code == 200
    assert all(rec["type"] == "entity" for rec in r.json()["results"])


def test_search_returns_results(client):
    r = client.get("/search", params={"q": "orders"})
    assert r.status_code == 200
    names = [rec["name"] for rec in r.json()["results"]]
    assert "orders" in names


def test_search_type_filter(client):
    r = client.get("/search", params={"q": "orders", "type": "entity"})
    assert r.status_code == 200
    assert all(rec["type"] == "entity" for rec in r.json()["results"])


def test_search_missing_q_returns_422(client):
    r = client.get("/search")
    assert r.status_code == 422


def test_get_record_by_identity(client):
    scope = "/source/sales/database/prod/collection/public"
    r = client.get("/record", params={"name": "orders", "type": "entity", "scope": scope})
    assert r.status_code == 200
    assert r.json()["result"]["name"] == "orders"


def test_get_record_not_found(client):
    r = client.get("/record", params={"name": "ghost", "type": "entity", "scope": "/source/sales"})
    assert r.status_code == 404
