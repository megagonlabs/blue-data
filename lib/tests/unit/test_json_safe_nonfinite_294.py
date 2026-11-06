"""#294: NaN/±Infinity and memoryview in sampled data.

#264 coerced driver types to primitives but returned floats unchanged, so a sampled
``NaN`` / ``Infinity`` reached the store as a bare non-standard JSON token — RedisJSON
rejected it and a strict parser / FastAPI's encoder raised on a file store. And a
Postgres ``bytea`` arrives as ``memoryview``, which fell through to ``str()`` and was
stored as ``"<memory at 0x…>"``. json_safe now maps non-finite values to ``None`` and
reads a memoryview as bytes.
"""
import json
import os
import tempfile
from decimal import Decimal

import pytest

from blue_data.core.utils.json_utils import json_safe
from blue_data.registry.registry import Registry
from blue_data.source.json.file_json_source import FileJSONSource


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"),
                                   Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_becomes_none(value):
    assert json_safe(value) is None


@pytest.mark.parametrize("value,expected", [(1.5, 1.5), (0.0, 0.0), (Decimal("2.5"), 2.5)])
def test_finite_numbers_preserved(value, expected):
    assert json_safe(value) == expected


def test_memoryview_non_utf8_becomes_hex():
    assert json_safe(memoryview(b"\xff\x00")) == "ff00"


def test_memoryview_utf8_becomes_text():
    assert json_safe(memoryview(b"hi")) == "hi"


def test_output_is_strict_json():
    # json.dumps emits NaN/Infinity by default, but they are not valid JSON; the
    # coerced structure must parse under a strict parser (as RedisJSON / REST require).
    stats = {"min": float("-inf"), "max": float("inf"),
             "vals": [float("nan"), 1.5, Decimal("2.5")], "raw": memoryview(b"\xff\x01")}
    raw = json.dumps(json_safe(stats))

    def refuse(const):
        raise AssertionError(f"non-standard JSON constant {const}")

    parsed = json.loads(raw, parse_constant=refuse)  # must not raise
    assert parsed == {"min": None, "max": None, "vals": [None, 1.5, 2.5], "raw": "ff01"}


def test_file_store_round_trip_with_non_finite_values():
    # add → sync → stats stores stats via set_record_property; a sampled non-finite
    # value used to leave the file as invalid JSON (unreadable to strict JSON / REST).
    d = tempfile.mkdtemp()
    store = FileJSONSource(name="reg", properties={"connection": {"path": os.path.join(d, "reg.json")}})
    reg = Registry(store=store)
    reg.register_record(name="readings", type="entity", scope="/source/pg", description="", properties={})

    stats = {"sample_values": [float("nan"), float("inf"), 1.5], "raw": memoryview(b"\xff\x00")}
    reg.set_record_property("readings", "entity", "/source/pg", "stats", stats)

    raw = open(os.path.join(d, "reg.json"), encoding="utf-8").read()
    assert "NaN" not in raw and "Infinity" not in raw and "<memory at" not in raw

    def refuse(const):
        raise AssertionError(f"non-standard JSON constant {const}")

    json.loads(raw, parse_constant=refuse)  # strict parse of the persisted file
    rec = reg.get_record("readings", "entity", "/source/pg")
    assert rec["properties"]["stats"]["sample_values"] == [None, None, 1.5]
    assert rec["properties"]["stats"]["raw"] == "ff00"
