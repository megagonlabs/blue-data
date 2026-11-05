"""Regression tests for issue #265.

Since #212 the sanitizer matched secret words as substrings of the separator-stripped
key name, so ordinary configuration whose name merely *contained* a secret word was
deleted: max_tokens / token_limit / tokenizer (-> "token"), credentials_file
(-> "credential"), secret_manager_arn (-> "secret"), passages / bypass_cache /
compass_heading (-> "pass"). It also rewrote any URL with a ``host:port/…@`` shape and
blanked ``key=value`` inside free-text prose.

The matcher now splits the name on ``.``, ``_`` and ``-`` and treats a secret word as
secret only as the whole name or the final segment (with a ``*_key`` qualified by
``secret``/``private`` and a source-declared opt-in for names like
``aws_secret_access_key``). URI userinfo is stripped only when a password is actually
present, and the ``k=v`` redaction runs only on real connection strings. No services.
"""
import json

import pytest

from blue_data.registry.data_registry import (
    DataRegistry,
    _is_secret_key,
    _strip_uri_userinfo,
)
from blue_data.source.source import DataSource


# ---------- non-secret names survive (the reported regression) ----------

@pytest.mark.parametrize("key", [
    "max_tokens", "llm.max_tokens", "llm.price_per_input_token", "llm.price_per_output_token",
    "tokenizer", "token_limit", "passages", "bypass_cache", "compass_heading",
    "credentials_file", "secret_manager_arn", "aws_access_key_id", "partition_key",
    "keyspace", "scan_prefix",
])
def test_non_secret_names_not_flagged(key):
    assert _is_secret_key(key) is False


# ---------- real secrets are still flagged ----------

@pytest.mark.parametrize("key", [
    "password", "passwd", "passphrase", "pwd", "pass", "db_password", "sasl_password",
    "secret", "token", "auth_token", "access_token", "api_key", "apikey", "private_key",
    "authorization", "credential", "credentials", "aws_secret_access_key",
])
def test_secret_names_flagged(key):
    assert _is_secret_key(key) is True


def test_env_reference_names_preserved():
    assert _is_secret_key("password_env") is False
    assert _is_secret_key("aws_secret_access_key_env") is False


# ---------- URLs with a port / path '@' are not rewritten ----------

@pytest.mark.parametrize("url", [
    "https://example.com:8443/@acme/pkg",          # npm-style scope path, no userinfo
    "https://example.com:8443/feed?owner=a@b.c",   # '@' in the query string
    "redis://cache:6379/0",                        # host:port, no password
])
def test_url_without_password_is_untouched(url):
    assert _strip_uri_userinfo(url) == url


@pytest.mark.parametrize("url,expected", [
    ("postgresql://app:s3cret@db:5432/sales", "postgresql://app@db:5432/sales"),
    ("postgresql://u:x@s3cret@h:5432/db", "postgresql://u@h:5432/db"),  # '@' in password
    ("postgresql://u:s3cret/x@h:5432/db", "postgresql://u@h:5432/db"),  # '/' in password
])
def test_url_with_password_is_stripped(url, expected):
    assert _strip_uri_userinfo(url) == expected
    assert "s3cret" not in _strip_uri_userinfo(url)


# ---------- k=v redaction only on connection strings, not prose ----------

def test_prose_with_a_single_kv_is_left_alone():
    text = "password=never set here; ask ops"
    assert _strip_uri_userinfo(text) == text


def test_odbc_connection_string_password_redacted():
    out = _strip_uri_userinfo("Driver={PostgreSQL};Server=db;Uid=u;Pwd=s3cret")
    assert "s3cret" not in out
    assert "Driver={PostgreSQL}" in out and "Server=db" in out and "Uid=u" in out


# ---------- end-to-end: a rebuilt source keeps its configuration ----------

class _NoConnectSource(DataSource):
    """Base _connect is a no-op, so this registers/rebuilds without a live server."""


class _DeclaresSecrets(DataSource):
    _secret_properties = frozenset({"vault_handle"})  # a name the segment rule can't know


def test_configuration_round_trips_through_register_source():
    props = {
        "max_tokens": 1024, "llm.max_tokens": 256,
        "llm.price_per_input_token": 1e-6, "llm.price_per_output_token": 2e-6,
        "tokenizer": "cl100k_base", "token_limit": 8000,
        "credentials_file": "/opt/app/creds.json", "secret_manager_arn": "arn:x",
        "endpoint": "https://example.com:8443/@acme/pkg",
        "password": "PLACEHOLDER",  # the one real secret
    }
    reg = DataRegistry()
    reg.register_source(_NoConnectSource("s", properties=dict(props)))
    stored = reg.get_record("s", "source", "/")["properties"]
    for key, value in props.items():
        if key == "password":
            assert key not in stored
        else:
            assert stored.get(key) == value
    assert "PLACEHOLDER" not in json.dumps(stored)


def test_source_declared_secret_is_stripped():
    reg = DataRegistry()
    reg.register_source(_DeclaresSecrets("s", properties={"vault_handle": "PLACEHOLDER", "region": "us"}))
    stored = reg.get_record("s", "source", "/")["properties"]
    assert "vault_handle" not in stored
    assert stored["region"] == "us"
