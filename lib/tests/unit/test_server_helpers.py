"""#116 — shared blue_data.server helpers: bind resolution, mandatory-by-default
API-key auth, and the CSRF content-type guard (reused by all platform services)."""
import types

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException

from blue_data.server import make_api_key_guard, make_csrf_guard, resolve_bind


def _req(path="/data", headers=None, method="GET"):
    return types.SimpleNamespace(
        url=types.SimpleNamespace(path=path),
        headers=headers or {},
        method=method,
    )


# ---------- resolve_bind ----------

def test_resolve_bind_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("BLUE_DATA_API_HOST", raising=False)
    monkeypatch.delenv("BLUE_DATA_API_PORT", raising=False)
    assert resolve_bind("BLUE_DATA_API", 8000) == ("127.0.0.1", 8000)


def test_resolve_bind_reads_env_and_prefix(monkeypatch):
    monkeypatch.setenv("BLUE_DOC_API_HOST", "0.0.0.0")
    monkeypatch.setenv("BLUE_DOC_API_PORT", "8001")
    assert resolve_bind("BLUE_DOC_API", 9999) == ("0.0.0.0", 8001)


# ---------- api-key guard (mandatory by default) ----------

def test_api_key_mandatory_by_default(monkeypatch):
    monkeypatch.delenv("SVC_KEY", raising=False)
    monkeypatch.delenv("SVC_AUTH_DISABLED", raising=False)
    guard = make_api_key_guard("SVC")
    with pytest.raises(HTTPException) as e:
        guard(_req())
    assert e.value.status_code == 401
    guard(_req(path="/health"))  # open path: no raise


def test_api_key_explicit_disable(monkeypatch):
    monkeypatch.delenv("SVC_KEY", raising=False)
    monkeypatch.setenv("SVC_AUTH_DISABLED", "true")
    make_api_key_guard("SVC")(_req())  # no raise


def test_api_key_enforced_when_set(monkeypatch):
    monkeypatch.setenv("SVC_KEY", "secret")
    guard = make_api_key_guard("SVC")
    with pytest.raises(HTTPException):
        guard(_req(headers={}))
    guard(_req(headers={"x-api-key": "secret"}))                 # header
    guard(_req(headers={"authorization": "Bearer secret"}))      # bearer
    with pytest.raises(HTTPException):
        guard(_req(headers={"x-api-key": "wrong"}))


def test_api_key_compared_in_constant_time(monkeypatch):
    """#243 — the key check uses hmac.compare_digest, not !=."""
    import blue_data.server as server

    calls = []
    real = server.hmac.compare_digest
    monkeypatch.setattr(server.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))
    monkeypatch.setenv("SVC_KEY", "sécret")
    guard = make_api_key_guard("SVC")
    guard(_req(headers={"x-api-key": "sécret"}))  # non-ASCII key still matches
    with pytest.raises(HTTPException):
        guard(_req(headers={"x-api-key": "sécreT"}))
    assert calls == [("sécret".encode(), "sécret".encode()), ("sécreT".encode(), "sécret".encode())]


# ---------- CSRF guard ----------

def test_csrf_rejects_form_content_type_on_writes():
    guard = make_csrf_guard()
    with pytest.raises(HTTPException) as e:
        guard(_req(method="POST", headers={"content-type": "application/x-www-form-urlencoded"}))
    assert e.value.status_code == 415


def test_csrf_allows_json_and_reads():
    guard = make_csrf_guard()
    guard(_req(method="POST", headers={"content-type": "application/json"}))  # ok
    guard(_req(method="PUT", headers={}))                                     # bodyless ok
    guard(_req(method="GET", headers={"content-type": "text/plain"}))         # non-mutating ok
