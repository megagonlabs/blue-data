"""#90 — REST API security: /query is read-only by default, writes require an
explicit server opt-in, and API-key auth is enforced when configured."""
import pytest


def test_query_drop_without_commit_is_blocked(client):
    r = client.post("/sales/query", json={"query": "DROP TABLE orders", "database": "prod"})
    assert r.status_code == 400  # blocked by the read-only guard, not committed
    survived = client.post("/sales/query", json={"query": "SELECT * FROM orders", "database": "prod"})
    assert survived.status_code == 200


def test_query_commit_requires_writes_enabled(client, monkeypatch):
    monkeypatch.delenv("BLUE_DATA_API_ALLOW_WRITES", raising=False)
    r = client.post(
        "/sales/query",
        json={"query": "DROP TABLE orders", "database": "prod", "commit": True},
    )
    assert r.status_code == 403


def test_query_commit_allowed_when_writes_enabled(client, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_API_ALLOW_WRITES", "true")
    r = client.post(
        "/sales/query",
        json={"query": "DELETE FROM orders WHERE id = 999", "database": "prod", "commit": True},
    )
    assert r.status_code == 200


def test_select_is_read_only_and_works(client):
    r = client.post("/sales/query", json={"query": "SELECT * FROM orders", "database": "prod"})
    assert r.status_code == 200
    assert isinstance(r.json()["results"], list)


def test_auth_enforced_when_key_set(client, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_API_KEY", "secret")
    assert client.get("/sources").status_code == 401
    assert client.get("/sources", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/sources", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert client.get("/health").status_code == 200  # health stays open


def test_auth_disabled_when_key_unset(client, monkeypatch):
    monkeypatch.delenv("BLUE_DATA_API_KEY", raising=False)
    assert client.get("/sources").status_code == 200


def test_wrong_api_key_rejected(client, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_API_KEY", "secret")
    assert client.get("/sources", headers={"X-API-Key": "nope"}).status_code == 401


@pytest.mark.parametrize("method,path,body", [
    ("get", "/sources", None),
    ("post", "/sales/query", {"query": "SELECT 1", "database": "prod"}),
    ("put", "/sales/sync", None),
    ("delete", "/sales", None),
])
def test_auth_enforced_across_mutating_and_read_endpoints(client, monkeypatch, method, path, body):
    monkeypatch.setenv("BLUE_DATA_API_KEY", "secret")
    call = getattr(client, method)
    kwargs = {"json": body} if body is not None else {}
    assert call(path, **kwargs).status_code == 401
    assert call(path, headers={"X-API-Key": "secret"}, **kwargs).status_code != 401


def test_commit_write_persists_when_enabled(client, monkeypatch):
    monkeypatch.setenv("BLUE_DATA_API_ALLOW_WRITES", "true")
    ins = client.post("/sales/query", json={
        "query": "INSERT INTO orders VALUES (777, 1, 5.0, 'completed')",
        "database": "prod", "commit": True,
    })
    assert ins.status_code == 200
    back = client.post("/sales/query", json={
        "query": "SELECT * FROM orders WHERE id = 777", "database": "prod",
    })
    assert back.status_code == 200
    assert len(back.json()["results"]) == 1


def test_run_binds_loopback_by_default(monkeypatch):
    import registry_api.main as m
    monkeypatch.delenv("BLUE_DATA_API_HOST", raising=False)
    monkeypatch.delenv("BLUE_DATA_API_PORT", raising=False)
    captured = {}
    monkeypatch.setattr(m.uvicorn, "run", lambda *a, **k: captured.update(k))
    m.run()
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000


def test_run_respects_host_and_port_env(monkeypatch):
    import registry_api.main as m
    monkeypatch.setenv("BLUE_DATA_API_HOST", "0.0.0.0")
    monkeypatch.setenv("BLUE_DATA_API_PORT", "9001")
    captured = {}
    monkeypatch.setattr(m.uvicorn, "run", lambda *a, **k: captured.update(k))
    m.run()
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9001
