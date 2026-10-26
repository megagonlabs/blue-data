"""Regression tests for issue #100.

(a) The credential sanitizer only stripped exact key names directly under
    properties["connection"], leaking passwords inside URIs, nested dicts, and
    alias keys through get_record.
(b) Stripped passwords were kept nowhere, so a persisted source couldn't reconnect.

The sanitizer is now recursive (deny-list at any depth) and strips URI userinfo
passwords; credentials can be stored as ``<key>_env`` references that connect_source
resolves from the environment. No real database is needed.
"""
import json

from blue_data.registry.data_registry import (
    DataRegistry,
    _resolve_credential_references,
    _sanitize_properties,
)
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.source import DataSource


class _NoConnectSource(DataSource):
    """Base _connect is a no-op, so this can be rebuilt without a live server."""


MARK = "PLACEHOLDER-CREDENTIAL"


# ---------- (a) recursive sanitize + URI userinfo stripping ----------

def test_sanitize_strips_uri_nested_and_alias_keys():
    clean = _sanitize_properties({"connection": {
        "uri": f"postgresql://app:{MARK}@db.example:5432/sales",
        "options": {"password": MARK},
        "pass": MARK,
    }})
    assert json.dumps(clean).count(MARK) == 0
    assert clean["connection"]["uri"] == "postgresql://app@db.example:5432/sales"
    assert clean["connection"]["options"] == {}
    assert "pass" not in clean["connection"]


def test_get_record_has_no_credentials_but_live_source_keeps_them():
    reg = DataRegistry()
    reg.register_source(_NoConnectSource("s", properties={"connection": {
        "uri": f"postgresql://app:{MARK}@h:5432/db",
        "options": {"password": MARK},
        "pass": MARK,
    }}))
    assert json.dumps(reg.get_record("s", "source", "/")).count(MARK) == 0
    assert reg.get_source("s").properties["connection"]["pass"] == MARK  # in-process only


def test_reference_key_is_preserved_but_plaintext_stripped():
    clean = _sanitize_properties(
        {"connection": {"host": "h", "password": MARK, "password_env": "PGPASSWORD"}}
    )
    assert clean["connection"]["password_env"] == "PGPASSWORD"
    assert "password" not in clean["connection"]


# ---------- (b) reference resolution and reconnect ----------

def test_resolve_credential_reference_from_env(monkeypatch):
    monkeypatch.setenv("BD_TEST_PW", "s3cret")
    resolved = _resolve_credential_references(
        {"connection": {"host": "h", "password_env": "BD_TEST_PW"}}
    )
    assert resolved["connection"]["password"] == "s3cret"
    assert resolved["connection"]["password_env"] == "BD_TEST_PW"


def test_resolve_does_not_override_an_explicit_value(monkeypatch):
    monkeypatch.setenv("BD_TEST_PW", "fromenv")
    resolved = _resolve_credential_references(
        {"connection": {"password": "explicit", "password_env": "BD_TEST_PW"}}
    )
    assert resolved["connection"]["password"] == "explicit"


def test_persisted_source_reconnects_via_reference(monkeypatch):
    monkeypatch.setenv("BD_TEST_PW", "s3cret")
    store = MemoryJSONSource()

    reg1 = DataRegistry(store=store)
    reg1.register_source(_NoConnectSource(
        "s", properties={"connection": {"host": "h", "password_env": "BD_TEST_PW"}}
    ))

    # "restart": a new registry over the same store has an empty live-source dict.
    reg2 = DataRegistry(store=store)
    rebuilt = reg2.connect_source("s")

    assert rebuilt is not None
    assert rebuilt.properties["connection"]["password"] == "s3cret"
    # the persisted record never carried the secret
    assert json.dumps(reg2.get_record("s", "source", "/")).count("s3cret") == 0
