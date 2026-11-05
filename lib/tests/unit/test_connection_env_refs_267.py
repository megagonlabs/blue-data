"""Regression tests for issue #267.

``<key>_env`` references (e.g. ``password_env``) let a password-protected source keep
its secret out of the persisted record and still connect — the sanitizer strips literal
passwords, so a reference is the only thing that survives a registry rebuild (design/14
§3). Resolution used to live only in the SQL base, so Neo4j, MongoDB and Redis sources
could not use ``password_env`` when built directly. Resolution now happens once in
``DataSource._start_connection``, so every source gets it. No external services.
"""
from blue_data.source.source import DataSource


class _Spy(DataSource):
    """Records the kwargs its ``_connect`` receives, without a real server."""

    def _connect(self, **connection):
        self.seen = connection
        return object()


# ---------- the base resolver (pure function) ----------

def test_resolves_reference_into_base_key(monkeypatch):
    monkeypatch.setenv("BD_PW", "s3cret")
    out = DataSource._resolve_connection_env_refs({"host": "h", "password": "", "password_env": "BD_PW"})
    assert out == {"host": "h", "password": "s3cret"}  # resolved, reference stripped


def test_explicit_non_empty_value_wins(monkeypatch):
    monkeypatch.setenv("BD_PW", "fromenv")
    out = DataSource._resolve_connection_env_refs({"password": "explicit", "password_env": "BD_PW"})
    assert out == {"password": "explicit"}  # #239: a set value is not masked


def test_missing_env_var_leaves_base_and_drops_reference(monkeypatch):
    monkeypatch.delenv("BD_MISSING_267", raising=False)
    out = DataSource._resolve_connection_env_refs({"password": "", "password_env": "BD_MISSING_267"})
    # Reference always dropped so a driver never sees 'password_env' (#207); base untouched.
    assert out == {"password": ""}


def test_reference_dropped_even_when_base_absent(monkeypatch):
    monkeypatch.setenv("BD_PW", "s3cret")
    out = DataSource._resolve_connection_env_refs({"username_env": "BD_PW"})
    assert out == {"username": "s3cret"}


def test_non_string_reference_ignored():
    out = DataSource._resolve_connection_env_refs({"password": "", "password_env": {"not": "a name"}})
    assert out == {"password": ""}  # malformed reference dropped, base left as-is


def test_non_dict_passthrough():
    assert DataSource._resolve_connection_env_refs(None) is None


# ---------- end to end: every source resolves at construction ----------

def test_source_built_with_password_env_connects_with_resolved_secret(monkeypatch):
    monkeypatch.setenv("BD_PW", "s3cret")
    s = _Spy("s", properties={"connection": {"host": "h", "password": "", "password_env": "BD_PW"}})
    assert s.seen["password"] == "s3cret"          # _connect saw the resolved secret
    assert "password_env" not in s.seen            # and not the reference
    # The live source keeps the reference, not a resolved literal — so re-persisting it
    # stores the reference, never the secret.
    assert s.properties["connection"]["password_env"] == "BD_PW"
    assert s.properties["connection"]["password"] == ""


def test_literal_and_reference_prefers_literal(monkeypatch):
    monkeypatch.setenv("BD_PW", "fromenv")
    s = _Spy("s", properties={"connection": {"password": "literal", "password_env": "BD_PW"}})
    assert s.seen["password"] == "literal"
    assert "password_env" not in s.seen
