"""Regression tests for issue #212.

The credential sanitizer matched only an exact key-name list and a URI regex that
stopped at the first '/' or '@', so many common secret forms were persisted and returned
by get_record: db_password, sasl_password, passphrase, auth_token, aws_secret_access_key,
Authorization header values, ODBC Pwd=, and URI passwords containing '/' or '@'.

Key matching is now substring-based (normalized), URIs are stripped with urlsplit plus a
'/'-in-password backstop, and ODBC/JDBC k=v; secrets are redacted — while non-secret keys
and the *_env reference keys are preserved. No external services.
"""
import json

import pytest

from blue_data.registry.data_registry import (
    DataRegistry,
    _resolve_credential_references,
    _sanitize_properties,
)
from blue_data.source.source import DataSource

S = "PLACEHOLDER"  # fake secret marker


class _Dummy(DataSource):
    """Base _connect is a no-op, so this registers/rebuilds without a live server."""


# ---------- every secret form is stripped from the stored record ----------

@pytest.mark.parametrize("connection", [
    {"db_password": S},
    {"sasl_password": S},
    {"passphrase": S},
    {"auth_token": S},
    {"aws_secret_access_key": S},
    {"headers": {"Authorization": f"Bearer {S}"}},
    {"dsn": f"Driver=x;Server=h;Uid=u;Pwd={S};"},
    {"url": f"postgresql://u:{S}/x@h:5432/db"},   # password contains '/'
    {"url": f"postgresql://u:x@{S}@h:5432/db"},   # password contains '@'
    {"password": S},                              # control
])
def test_secret_forms_are_not_persisted(connection):
    reg = DataRegistry()
    reg.register_source(_Dummy("s", properties={"connection": connection}))
    stored = reg.get_record("s", "source", "/")["properties"]
    assert S not in json.dumps(stored)
    # The live in-process source keeps the full credential.
    assert S in json.dumps(reg.get_source("s").properties)


# ---------- the host/key structure is kept; only the secret value goes ----------

def test_odbc_dsn_keeps_structure_drops_only_password():
    clean = _sanitize_properties({"connection": {"dsn": f"Driver=x;Server=h;Uid=u;Pwd={S};"}})
    dsn = clean["connection"]["dsn"]
    assert S not in dsn
    assert "Driver=x" in dsn and "Server=h" in dsn and "Uid=u" in dsn


def test_uri_password_stripped_user_and_host_kept():
    clean = _sanitize_properties({"connection": {"url": f"postgresql://app:{S}@db.example:5432/sales"}})
    assert clean["connection"]["url"] == "postgresql://app@db.example:5432/sales"


# ---------- non-secret keys survive (reconnection / config correctness) ----------

def test_non_secret_keys_are_preserved():
    props = {"connection": {
        "host": "h", "port": 5432, "user": "app", "username": "app",
        "aws_access_key_id": "AKIA-NOT-A-SECRET",  # an identifier, not a secret
        "partition_key": "id", "keyspace": "ks", "scan_prefix": "v:",
        "database_directory": "/data", "sslmode": "require",
    }}
    clean = _sanitize_properties(props)["connection"]
    assert clean == props["connection"]  # nothing stripped


def test_env_reference_keys_preserved_and_resolvable(monkeypatch):
    clean = _sanitize_properties({"connection": {"host": "h", "password_env": "PGPASSWORD"}})
    assert clean["connection"]["password_env"] == "PGPASSWORD"  # reference kept (not a secret value)

    monkeypatch.setenv("PGPASSWORD", "s3cret")
    resolved = _resolve_credential_references({"connection": {"host": "h", "password_env": "PGPASSWORD"}})
    assert resolved["connection"]["password"] == "s3cret"
    assert "password_env" not in resolved["connection"]
