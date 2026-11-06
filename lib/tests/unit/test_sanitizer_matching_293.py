"""Regression tests for issue #293.

The #265 segment matcher narrowed too far, so secret forms the pre-#265 sanitizer
removed were persisted again: camelCase keys (``lower()`` ran before the split, so they
were one segment), plurals / numbered / suffixed names (only an exact final segment
matched), a userinfo password containing digits-before-``/`` and a URL embedded in longer
text (the backstop ran only on a malformed port). And pagination tokens were wrongly
stripped. These pin the corrected matching without regressing the #265 preserves.
"""
import json
import tempfile

import pytest

from blue_data.registry.data_registry import (
    DataRegistry,
    _is_secret_key,
    _sanitize_properties,
)
from blue_data.source.json.file_json_source import FileJSONSource
from blue_data.source.json.memory_json_source import MemoryJSONSource


# ---------- secret forms that were being persisted are stripped again ----------

@pytest.mark.parametrize("key", [
    "dbPassword", "accessToken", "clientSecret", "awsSecretAccessKey", "xApiKey",  # camelCase
    "secrets", "tokens", "passwords", "api_keys",                                   # plurals
    "password1",                                                                    # trailing digit
    "password_old", "secret_value", "token_value", "authorization_header",          # qualifiers
])
def test_secret_key_forms_removed(key):
    assert _is_secret_key(key) is True
    assert "FAKE" not in json.dumps(_sanitize_properties({key: "FAKE"}))


def test_nested_under_secrets_dropped():
    assert _sanitize_properties({"secrets": {"db": "FAKE"}}) == {}


@pytest.mark.parametrize("url,expected", [
    ("postgresql://u:12/FAKE@h:5432/db", "postgresql://u@h:5432/db"),  # digits before '/'
    ("redis://:12/FAKE@h:6379/0", "redis://h:6379/0"),                 # empty user
])
def test_userinfo_password_with_slash_stripped(url, expected):
    assert _sanitize_properties({"v": url})["v"] == expected


def test_url_embedded_in_longer_text_stripped():
    v = "primary postgresql://u:FAKE@h:5432/db replica redis://:FAKE@h:6379/0"
    assert "FAKE" not in _sanitize_properties({"v": v})["v"]


# ---------- pagination tokens are NOT credentials ----------

@pytest.mark.parametrize("key", ["next_token", "page_token", "continuation_token", "sync_token"])
def test_pagination_tokens_preserved(key):
    assert _is_secret_key(key) is False


# ---------- #265 preserves must still hold (no over-reach) ----------

@pytest.mark.parametrize("key", [
    "max_tokens", "llm.max_tokens", "llm.price_per_input_token", "llm.price_per_output_token",
    "tokenizer", "token_limit", "passages", "bypass_cache", "compass_heading",
    "credentials_file", "secret_manager_arn", "aws_access_key_id", "partition_key", "keyspace",
])
def test_non_secret_still_preserved(key):
    assert _is_secret_key(key) is False


@pytest.mark.parametrize("url", [
    "https://example.com:8443/@acme/pkg",         # npm-style scope path, not userinfo
    "https://example.com:8443/feed?owner=a@b.c",  # '@' in the query string
])
def test_scope_and_query_urls_untouched(url):
    assert _sanitize_properties({"v": url})["v"] == url


def test_standard_and_at_in_password_urls_still_stripped():
    assert _sanitize_properties(
        {"v": "postgresql://app:s3cret@db.example:5432/sales"}
    )["v"] == "postgresql://app@db.example:5432/sales"
    assert "PLACEHOLDER" not in _sanitize_properties(
        {"v": "postgresql://u:x@PLACEHOLDER@h:5432/db"}
    )["v"]


# ---------- end to end: stored record / registry file hold no secret ----------

def test_camelcase_credentials_not_in_stored_record():
    path = tempfile.mktemp(suffix=".json")
    reg = DataRegistry(store=FileJSONSource("st", properties={"connection": {"path": path}}))
    reg.register_source(MemoryJSONSource(
        "s", properties={"connection": {"dbPassword": "FAKE-PW", "accessToken": "FAKE-TOKEN"}}
    ))
    conn = reg.get_source_record("s")["properties"]["connection"]
    assert "dbPassword" not in conn and "accessToken" not in conn
    raw = open(path).read()
    assert "FAKE-PW" not in raw and "FAKE-TOKEN" not in raw
    # the live source keeps the full credentials
    assert reg.get_source("s").properties["connection"]["dbPassword"] == "FAKE-PW"
