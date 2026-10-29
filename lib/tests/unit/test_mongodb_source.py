"""Regression tests for issue #209.

MongoDBSource used its registry protocol tag ("json/mongodb") as the connection-URI
scheme, so pymongo raised InvalidURI for the documented {host, port} properties, and
it interpolated credentials into the URI unescaped. _connect now uses the mongodb
scheme independent of the protocol tag and passes credentials as kwargs (pymongo
escapes them). Server-free: MongoClient is mocked to capture what _connect builds.
"""
from unittest.mock import patch

import pytest

pytest.importorskip("pymongo")
from blue_data.source.json.mongodb import mongodb_json_source as mod
from blue_data.source.json.mongodb.mongodb_json_source import MongoDBSource


def _capture(conn):
    calls = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

        def close(self):
            pass

    with patch.object(mod, "MongoClient", _FakeClient):
        MongoDBSource("m", properties={"connection": conn})
    return calls


def test_documented_properties_use_host_port_kwargs_not_protocol_tag():
    calls = _capture({"host": "127.0.0.1", "port": 47117})
    assert calls["kwargs"].get("host") == "127.0.0.1"
    assert calls["kwargs"].get("port") == 47117
    assert "json/mongodb" not in str(calls)  # the protocol tag is never a URI scheme


def test_credentials_passed_as_kwargs_not_interpolated_into_uri():
    calls = _capture({"host": "h", "port": 1, "username": "u", "password": "p@ss:w/d"})
    assert calls["kwargs"]["username"] == "u"
    assert calls["kwargs"]["password"] == "p@ss:w/d"
    # The special-char password must not be interpolated into a URI string.
    assert not any("p@ss:w/d" in str(a) for a in calls["args"])


def test_port_is_coerced_to_int():
    calls = _capture({"host": "h", "port": "47117"})
    assert calls["kwargs"]["port"] == 47117


def test_srv_scheme_builds_srv_uri_without_port():
    calls = _capture({"host": "cluster.example.net", "scheme": "mongodb+srv",
                      "username": "u", "password": "p"})
    assert calls["kwargs"]["host"] == "mongodb+srv://cluster.example.net"
    assert "port" not in calls["kwargs"]
    assert calls["kwargs"]["username"] == "u"
