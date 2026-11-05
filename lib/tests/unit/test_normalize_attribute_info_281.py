"""#281: sync normalises an attribute's string ``info`` to a ``{"type": ...}``
mapping so every registry consumer (source inspect, enrichment metadata,
description generation) can read ``info["type"]`` without crashing.
"""
from blue_data.registry.data_registry import _normalize_attribute_info


def test_string_info_becomes_type_mapping():
    attrs = {"title": {"info": "str"}, "age": {"info": "int"}}
    _normalize_attribute_info(attrs)
    assert attrs["title"]["info"] == {"type": "str"}
    assert attrs["age"]["info"] == {"type": "int"}


def test_dict_info_left_unchanged():
    attrs = {"col": {"info": {"type": "INTEGER", "values": []}}}
    _normalize_attribute_info(attrs)
    assert attrs["col"]["info"] == {"type": "INTEGER", "values": []}


def test_missing_info_left_absent():
    attrs = {"col": {"semantic_type": "id"}}
    _normalize_attribute_info(attrs)
    assert "info" not in attrs["col"]  # consumers already tolerate missing info


def test_non_dict_values_ignored():
    attrs = {"weird": "not-a-dict"}
    _normalize_attribute_info(attrs)  # must not raise
    assert attrs["weird"] == "not-a-dict"
