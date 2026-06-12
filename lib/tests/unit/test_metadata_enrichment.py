"""Unit tests for MetaData deterministic enrichment methods.

These tests do not require an LLM — they exercise only the signal helpers,
value-axis inference, semantic-role inference, process-semantics inference,
quantitative-VST inference, and semantic-link detection.
"""
from __future__ import annotations

import pytest

from registry.enrichment.metadata import MetaData


@pytest.fixture
def md():
    return MetaData(llm_fn=None)


# ------------------------------------------------------------------ helpers

def _attr(name, semantic_type, sample_values=None, is_identifier=False):
    return {
        "name": name,
        "properties": {
            "value_semantics": {
                "semantic_type": semantic_type,
                "is_identifier": is_identifier,
            },
            "stats": {"sample_values": sample_values or []},
        },
    }


# ------------------------------------------------------------------ grouped_distribution_signal

def test_grouped_distribution_detects_spread(md):
    group = _attr("status", "ENUM_CATEGORY", sample_values=["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"])
    value = _attr("amount", "FLOAT", sample_values=[100, 200, 100, 200, 100, 200, 100, 200, 100, 200])
    assert md.grouped_distribution_signal(group, value) is True


def test_grouped_distribution_rejects_flat(md):
    group = _attr("status", "ENUM_CATEGORY", sample_values=["A", "B", "A", "B"])
    value = _attr("amount", "FLOAT", sample_values=[100, 100, 100, 100])
    assert md.grouped_distribution_signal(group, value) is False


def test_grouped_distribution_requires_two_groups(md):
    group = _attr("status", "ENUM_CATEGORY", sample_values=["A", "A", "A", "A", "A"])
    value = _attr("amount", "FLOAT", sample_values=[1, 2, 3, 4, 5])
    assert md.grouped_distribution_signal(group, value) is False


# ------------------------------------------------------------------ functional_dependency_signal

def test_functional_dependency_high_correlation(md):
    xs = list(range(1, 20))
    ys = [x * 2 for x in xs]
    a = _attr("x", "INTEGER", sample_values=xs)
    b = _attr("y", "INTEGER", sample_values=ys)
    assert md.functional_dependency_signal(a, b) is True


def test_functional_dependency_no_correlation(md):
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ys = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    a = _attr("x", "INTEGER", sample_values=xs)
    b = _attr("y", "INTEGER", sample_values=ys)
    assert md.functional_dependency_signal(a, b) is False


def test_functional_dependency_requires_min_samples(md):
    a = _attr("x", "INTEGER", sample_values=[1, 2, 3])
    b = _attr("y", "INTEGER", sample_values=[2, 4, 6])
    assert md.functional_dependency_signal(a, b) is False


# ------------------------------------------------------------------ infer_semantic_links (no duplicate bidirectional)

def test_no_duplicate_functional_dep_links(md):
    xs = list(range(1, 20))
    ys = [x * 2 for x in xs]
    a = _attr("x", "FLOAT", sample_values=xs)
    b = _attr("y", "FLOAT", sample_values=ys)
    links = md.infer_semantic_links([a, b])
    func_links = [l for l in links if isinstance(l["signal"], dict) and l["signal"].get("type") == "functional_dependency"]
    assert len(func_links) == 1, "functional_dependency must appear once per pair, not bidirectionally"


# ------------------------------------------------------------------ infer_semantic_role

def test_semantic_role_identifier(md):
    attr = {**_attr("user_id", "UUID"), "properties": {
        "value_semantics": {"semantic_type": "UUID", "is_identifier": True},
        "stats": {},
    }}
    role = md.infer_semantic_role(attr, [attr], [])
    assert role["primary_role"] == "IDENTIFIER"


def test_semantic_role_event_time(md):
    attr = _attr("created_at", "DATETIME")
    role = md.infer_semantic_role(attr, [attr], [])
    assert role["primary_role"] == "EVENT_TIME"


def test_semantic_role_descriptive_fallback(md):
    attr = _attr("description", "FREE_TEXT")
    role = md.infer_semantic_role(attr, [attr], [])
    assert role["primary_role"] == "DESCRIPTIVE"


# ------------------------------------------------------------------ infer_quantitative_vst_role

def test_qvst_currency(md):
    attr = _attr("price", "CURRENCY_AMOUNT", sample_values=[9.99, 14.99, 4.99])
    result = md.infer_quantitative_vst_role(attr)
    assert result is not None
    assert result["role"] == "MEASUREMENT"


def test_qvst_percentage(md):
    attr = _attr("discount", "PERCENTAGE", sample_values=[0.1, 0.2, 0.15])
    result = md.infer_quantitative_vst_role(attr)
    assert result is not None
    assert result["role"] == "COMPUTATIONAL"


def test_qvst_skips_non_numeric(md):
    attr = _attr("name", "STRING", sample_values=["alice", "bob"])
    result = md.infer_quantitative_vst_role(attr)
    assert result is None


# ------------------------------------------------------------------ infer_process_semantics

def _make_row_samples(n=20):
    import datetime
    base = datetime.date(2023, 1, 1)
    rows = []
    for i in range(n):
        rows.append({
            "user_id": i % 5,
            "event_date": str(base + datetime.timedelta(days=i)),
            "amount": float(i * 10),
        })
    return rows


def _make_attrs_for_process():
    return [
        {
            "name": "user_id",
            "properties": {
                "value_semantics": {"semantic_type": "INTEGER", "is_identifier": True},
                "stats": {},
                "semantic_role": {},
            },
        },
        {
            "name": "event_date",
            "properties": {
                "value_semantics": {"semantic_type": "DATE", "is_identifier": False},
                "stats": {},
                "semantic_role": {"primary_role": "EVENT_TIME"},
            },
        },
        {
            "name": "amount",
            "properties": {
                "value_semantics": {"semantic_type": "FLOAT", "is_identifier": False},
                "stats": {},
                "semantic_role": {},
            },
        },
    ]


def test_process_semantics_detected(md):
    rows = _make_row_samples(20)
    attrs = _make_attrs_for_process()
    result = md.infer_process_semantics("events", attrs, rows)
    assert result is not None
    assert result["row_semantics"] == "EVENT"
    assert result["event_time"] == "event_date"


def test_process_semantics_requires_min_rows(md):
    rows = _make_row_samples(5)
    attrs = _make_attrs_for_process()
    result = md.infer_process_semantics("events", attrs, rows)
    assert result is None


def test_process_semantics_requires_time_attr(md):
    rows = _make_row_samples(20)
    attrs = [
        {"name": "user_id", "properties": {"value_semantics": {"semantic_type": "INTEGER", "is_identifier": True}, "stats": {}, "semantic_role": {}}},
        {"name": "amount",  "properties": {"value_semantics": {"semantic_type": "FLOAT", "is_identifier": False}, "stats": {}, "semantic_role": {}}},
    ]
    result = md.infer_process_semantics("events", attrs, rows)
    assert result is None


# ------------------------------------------------------------------ infer_attribute_process_roles — STATE_VARIABLE reachable

def test_state_variable_role_assigned(md):
    attrs = [
        {
            "name": "score",
            "properties": {
                "value_semantics": {"semantic_type": "INTEGER", "is_identifier": False},
                "stats": {},
                "semantic_role": {"primary_role": "EVIDENCE"},
            },
        },
    ]
    ps = {"event_time": "ts", "entity_keys": ["user_id"]}
    roles = md.infer_attribute_process_roles(attrs, ps)
    assert roles.get("score", {}).get("process_vst_role") == "STATE_VARIABLE"


def test_event_measure_role_assigned(md):
    attrs = [
        {
            "name": "revenue",
            "properties": {
                "value_semantics": {"semantic_type": "CURRENCY_AMOUNT", "is_identifier": False},
                "stats": {},
                "semantic_role": {},
            },
        },
    ]
    ps = {"event_time": "ts", "entity_keys": []}
    roles = md.infer_attribute_process_roles(attrs, ps)
    assert roles.get("revenue", {}).get("process_vst_role") == "EVENT_MEASURE"


# ------------------------------------------------------------------ is_value_axis_eligible

def test_value_axis_eligible_numeric(md):
    attr = _attr("amount", "CURRENCY_AMOUNT")
    assert md.is_value_axis_eligible(attr) is True


def test_value_axis_not_eligible_identifier(md):
    attr = {**_attr("id", "INTEGER"), "properties": {
        "value_semantics": {"semantic_type": "INTEGER", "is_identifier": True},
        "stats": {},
    }}
    assert md.is_value_axis_eligible(attr) is False


def test_value_axis_not_eligible_enum(md):
    attr = _attr("category", "ENUM_CATEGORY")
    assert md.is_value_axis_eligible(attr) is False
