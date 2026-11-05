"""#264: registry stats must serialize on file/Redis stores.

Postgres/MySQL return date/Decimal and MongoDB returns ObjectId/bytes in source
stats. The registry persists records as JSON, so these must be coerced to
primitives at the write boundary — otherwise collect_source_stats / enrich /
metadata crash with "Object of type X is not JSON serializable".
"""
import datetime
import json
import os
import tempfile
from decimal import Decimal

from blue_data.core.utils.json_utils import json_safe
from blue_data.registry.registry import Registry
from blue_data.source.json.file_json_source import FileJSONSource


class _FakeObjectId:
    """Stand-in for bson.ObjectId — an exotic type json can't serialize."""
    def __str__(self):
        return "66b0c0ffeecafe0000000001"


def test_json_safe_coerces_driver_types():
    stats = {
        "day": datetime.date(2026, 1, 2),
        "ts": datetime.datetime(2026, 1, 2, 3, 4, 5),
        "amount": Decimal("1.50"),
        "blob": b"bytes",
        "oid": _FakeObjectId(),
        "sample_values": [datetime.date(2026, 1, 3), Decimal("2.5"), _FakeObjectId()],
        "nested": {"when": datetime.time(9, 30)},
        "tags": {"a", "b"},
    }
    safe = json_safe(stats)
    json.dumps(safe)  # must not raise

    assert safe["day"] == "2026-01-02"
    assert safe["ts"] == "2026-01-02T03:04:05"
    assert safe["amount"] == 1.5
    assert safe["blob"] == "bytes"
    assert safe["oid"] == "66b0c0ffeecafe0000000001"
    assert safe["sample_values"] == ["2026-01-03", 2.5, "66b0c0ffeecafe0000000001"]
    assert safe["nested"] == {"when": "09:30:00"}
    assert sorted(safe["tags"]) == ["a", "b"]


def test_json_safe_passes_primitives_through():
    assert json_safe({"a": 1, "b": "x", "c": True, "d": None, "e": 1.5}) == {
        "a": 1, "b": "x", "c": True, "d": None, "e": 1.5
    }


def test_json_safe_non_utf8_bytes_falls_back_to_hex():
    assert json_safe(b"\xff\xfe") == "fffe"


def test_set_record_property_persists_driver_values_to_file_store():
    # The documented workflow (add → sync → stats) stores stats via
    # set_record_property; with a file store the raw driver values used to crash
    # json.dump. They must now persist and round-trip as primitives (#264).
    d = tempfile.mkdtemp()
    store = FileJSONSource(name="reg", properties={"connection": {"path": os.path.join(d, "reg.json")}})
    reg = Registry(store=store)
    reg.register_record(name="orders", type="entity", scope="/source/pg", description="", properties={})

    stats = {"sample_values": [datetime.date(2026, 1, 2), Decimal("1.50"), _FakeObjectId()]}
    reg.set_record_property("orders", "entity", "/source/pg", "stats", stats)  # pre-fix: raises

    # Persisted file is valid JSON …
    with open(os.path.join(d, "reg.json"), encoding="utf-8") as f:
        json.load(f)
    # … and reads back as primitives.
    rec = reg.get_record("orders", "entity", "/source/pg")
    assert rec["properties"]["stats"]["sample_values"] == [
        "2026-01-02", 1.5, "66b0c0ffeecafe0000000001"
    ]
