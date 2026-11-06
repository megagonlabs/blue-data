"""Regression tests for issue #269.

After #212/#265 the credential sanitizer still had gaps: it crashed on multi-host and
bad-port URIs, left secrets in URL query parameters / Authorization headers / header
lists, swallowed a libpq DSN's keywords after the password, and — most importantly —
``set_source_property`` and ``update_source`` wrote to the store with no sanitising at
all, so a credential set after registration was persisted. These pin the fixes. No
external services.
"""
import tempfile

import pytest

from blue_data.registry.data_registry import (
    DataRegistry,
    _sanitize_properties,
    _strip_uri_userinfo,
)
from blue_data.source.graph.memory_graph_source import MemoryGraphSource
from blue_data.source.json.file_json_source import FileJSONSource

MARK = "FAKE-SECRET"


def _file_registry():
    path = tempfile.mktemp(suffix=".json")
    return path, DataRegistry(store=FileJSONSource(properties={"connection": {"path": path}}))


# ---------- no crash on multi-host / bad-port URIs (and the password is stripped) ----------

@pytest.mark.parametrize("uri,expected", [
    (f"mongodb://u:{MARK}@h1:27017,h2:27017/db", "mongodb://u@h1:27017,h2:27017/db"),
    (f"redis://u:{MARK}@host:notaport/0", "redis://u@host:notaport/0"),
    (f"redis://u:{MARK}@host:99999/0", "redis://u@host:99999/0"),
])
def test_multi_host_and_bad_port_uris_do_not_crash(uri, expected):
    out = _strip_uri_userinfo(uri)
    assert out == expected
    assert MARK not in out


# ---------- secret URL query params, Authorization headers, and header lists ----------

def test_secret_url_query_param_is_blanked():
    out = _strip_uri_userinfo(f"https://h/api?access_token={MARK}&x=1")
    assert MARK not in out
    assert "x=1" in out  # non-secret params survive


def test_non_secret_query_untouched():
    url = "https://h/api?page=2&sort=asc"
    assert _strip_uri_userinfo(url) == url  # nothing secret -> not reserialised


def test_authorization_header_string_is_truncated():
    out = _strip_uri_userinfo(f"Authorization: Bearer {MARK}")
    assert out == "Authorization:"


def test_header_list_pair_with_secret_name_is_blanked():
    clean = _sanitize_properties({"headers": [["Authorization", f"Bearer {MARK}"], ["Accept", "json"]]})
    assert clean["headers"] == [["Authorization", ""], ["Accept", "json"]]


def test_header_dict_with_secret_name_is_dropped():
    clean = _sanitize_properties({"headers": {"Authorization": f"Bearer {MARK}", "Accept": "json"}})
    assert clean["headers"] == {"Accept": "json"}


# ---------- libpq (space-separated) DSN keeps the keywords after the password ----------

def test_libpq_dsn_keeps_keywords_after_password():
    out = _strip_uri_userinfo(f"host=db password={MARK} dbname=x sslmode=require")
    assert MARK not in out
    assert "dbname=x" in out and "sslmode=require" in out
    assert "password=" in out  # key kept, value blanked


def test_prose_with_one_kv_pair_still_untouched():
    text = "password=never set here; ask ops"  # the #265 prose case stays safe
    assert _strip_uri_userinfo(text) == text


# ---------- set_source_property / update_source sanitise like register_source ----------

def test_set_source_property_does_not_persist_secret_key():
    path, reg = _file_registry()
    reg.register_source(MemoryGraphSource("s", properties={}))
    reg.set_source_property("s", "api_token", "FAKE-TOKEN")
    assert "FAKE-TOKEN" not in open(path).read()


def test_set_source_property_strips_nested_secret():
    path, reg = _file_registry()
    reg.register_source(MemoryGraphSource("s", properties={}))
    reg.set_source_property("s", "connection", {"host": "h", "password": "FAKE-PW"})
    stored = reg.get_source_record("s")["properties"]
    assert "FAKE-PW" not in open(path).read()
    assert stored["connection"]["host"] == "h"          # non-secret kept
    assert "password" not in stored["connection"]        # secret dropped
    # the live source keeps the full credential
    assert reg.get_source("s").properties["connection"]["password"] == "FAKE-PW"


def test_update_source_strips_nested_secret():
    path, reg = _file_registry()
    reg.register_source(MemoryGraphSource("s", properties={}))
    reg.update_source("s", properties={"connection": {"host": "h", "password": "FAKE-PW-3"}})
    assert "FAKE-PW-3" not in open(path).read()
    assert reg.get_source_record("s")["properties"]["connection"]["host"] == "h"


def test_set_and_delete_source_property_accept_rebuild():
    # The REST route calls these with rebuild=True; they must accept it (#269).
    _, reg = _file_registry()
    reg.register_source(MemoryGraphSource("s", properties={}))
    reg.set_source_property("s", "description_note", "hello", rebuild=True)
    reg.delete_source_property("s", "description_note", rebuild=True)


def test_set_source_property_non_secret_roundtrips():
    path, reg = _file_registry()
    reg.register_source(MemoryGraphSource("s", properties={}))
    reg.set_source_property("s", "max_tokens", 1024)
    assert reg.get_source_record("s")["properties"]["max_tokens"] == 1024
