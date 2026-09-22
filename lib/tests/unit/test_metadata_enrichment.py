"""Unit tests for MetaData deterministic enrichment methods.

These tests do not require an LLM — they exercise only the signal helpers,
value-axis inference, semantic-role inference, process-semantics inference,
quantitative-VST inference, and semantic-link detection.
"""
from __future__ import annotations

import pytest

from blue_data.registry.enrichment.metadata import MetaData
from blue_data.registry.enrichment.metadata_utils import (
    functional_dependency_signal,
    grouped_distribution_signal,
    parse_timestamp,
)


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
    assert grouped_distribution_signal(group, value) is True


def test_grouped_distribution_rejects_flat(md):
    group = _attr("status", "ENUM_CATEGORY", sample_values=["A", "B", "A", "B"])
    value = _attr("amount", "FLOAT", sample_values=[100, 100, 100, 100])
    assert grouped_distribution_signal(group, value) is False


def test_grouped_distribution_requires_two_groups(md):
    group = _attr("status", "ENUM_CATEGORY", sample_values=["A", "A", "A", "A", "A"])
    value = _attr("amount", "FLOAT", sample_values=[1, 2, 3, 4, 5])
    assert grouped_distribution_signal(group, value) is False


# ------------------------------------------------------------------ functional_dependency_signal

def test_functional_dependency_high_correlation(md):
    xs = list(range(1, 20))
    ys = [x * 2 for x in xs]
    a = _attr("x", "INTEGER", sample_values=xs)
    b = _attr("y", "INTEGER", sample_values=ys)
    assert functional_dependency_signal(a, b) is True


def test_functional_dependency_no_correlation(md):
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ys = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    a = _attr("x", "INTEGER", sample_values=xs)
    b = _attr("y", "INTEGER", sample_values=ys)
    assert functional_dependency_signal(a, b) is False


def test_functional_dependency_requires_min_samples(md):
    a = _attr("x", "INTEGER", sample_values=[1, 2, 3])
    b = _attr("y", "INTEGER", sample_values=[2, 4, 6])
    assert functional_dependency_signal(a, b) is False


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


# ------------------------------------------------------------------ helpers for new tests

def _numeric_attr(name, semantic_type, sample_values, qvst_role=None, process_vst_role=None, safe_agg=None, semantic_role=None):
    props: dict = {
        "value_semantics": {"semantic_type": semantic_type, "is_identifier": False},
        "stats": {"sample_values": sample_values},
    }
    if qvst_role:
        props["quantitative_vst"] = {"role": qvst_role}
    if process_vst_role:
        props["process_vst_role"] = {"process_vst_role": process_vst_role}
    if safe_agg:
        props["safe_aggregation"] = safe_agg
    if semantic_role:
        props["semantic_role"] = {"primary_role": semantic_role}
    return {"name": name, "properties": props}


def _rows_with_spread(group_vals, value_map, n_per_group=6):
    """Build row_samples where group_attr → value_attr has a clear spread."""
    rows = []
    for g, v in value_map.items():
        rows.extend({group_vals: g, "value": v} for _ in range(n_per_group))
    return rows


# ------------------------------------------------------------------ validate_segments_signal

def test_validate_segments_detects_grouped_spread(md):
    g_attr = _attr("status", "ENUM_CATEGORY")
    v_attr = _attr("value", "FLOAT")
    rows = (
        [{"status": "LOW",  "value": 10.0}] * 8 +
        [{"status": "HIGH", "value": 90.0}] * 8
    )
    assert md.validate_segments_signal(g_attr, v_attr, rows) is True


def test_validate_segments_rejects_low_cooccurrence(md):
    g_attr = _attr("status", "ENUM_CATEGORY")
    v_attr = _attr("value", "FLOAT")
    rows = [{"status": "LOW", "value": 10.0}] * 3
    assert md.validate_segments_signal(g_attr, v_attr, rows) is False


def test_validate_segments_rejects_too_many_groups(md):
    g_attr = _attr("user_id", "INTEGER")
    v_attr = _attr("amount", "FLOAT")
    rows = [{"user_id": i, "amount": float(i * 10)} for i in range(30)]
    assert md.validate_segments_signal(g_attr, v_attr, rows) is False


def test_validate_segments_rejects_single_group(md):
    g_attr = _attr("type", "ENUM_CATEGORY")
    v_attr = _attr("value", "FLOAT")
    rows = [{"type": "A", "value": float(i)} for i in range(10)]
    assert md.validate_segments_signal(g_attr, v_attr, rows) is False


# ------------------------------------------------------------------ validate_temporal_alignment_signal

def test_validate_temporal_alignment_passes(md):
    a = _attr("event_date", "DATE")
    b = _attr("amount", "FLOAT")
    rows = [{"event_date": "2024-01-01", "amount": float(i)} for i in range(10)]
    assert md.validate_temporal_alignment_signal(a, b, rows) is True


def test_validate_temporal_alignment_rejects_non_temporal(md):
    a = _attr("category", "ENUM_CATEGORY")
    b = _attr("amount", "FLOAT")
    rows = [{"category": "A", "amount": float(i)} for i in range(10)]
    assert md.validate_temporal_alignment_signal(a, b, rows) is False


def test_validate_temporal_alignment_rejects_low_cooccurrence(md):
    a = _attr("event_date", "DATE")
    b = _attr("amount", "FLOAT")
    rows = [{"event_date": "2024-01-01", "amount": 1.0}] * 3
    assert md.validate_temporal_alignment_signal(a, b, rows) is False


# ------------------------------------------------------------------ validate_cooccurrence_signal

def test_validate_cooccurrence_passes(md):
    a = _attr("x", "INTEGER")
    b = _attr("y", "INTEGER")
    rows = [{"x": i, "y": i * 2} for i in range(10)]
    assert md.validate_cooccurrence_signal(a, b, rows) is True


def test_validate_cooccurrence_rejects_sparse(md):
    a = _attr("x", "INTEGER")
    b = _attr("y", "INTEGER")
    rows = [{"x": i, "y": i * 2} for i in range(3)]
    assert md.validate_cooccurrence_signal(a, b, rows) is False


# ------------------------------------------------------------------ validate_relational_link_signal

def test_relational_link_dispatches_grouped_distribution(md):
    g_attr = _attr("tier", "ENUM_CATEGORY")
    v_attr = _attr("revenue", "FLOAT")
    rows = (
        [{"tier": "basic",    "revenue": 10.0}] * 8 +
        [{"tier": "premium",  "revenue": 90.0}] * 8
    )
    result = md.validate_relational_link_signal(g_attr, v_attr, "grouped_distribution", rows)
    assert result is True


def test_relational_link_dispatches_temporal_alignment(md):
    a = _attr("created_at", "DATETIME")
    b = _attr("amount", "FLOAT")
    rows = [{"created_at": "2024-01-01", "amount": float(i)} for i in range(10)]
    result = md.validate_relational_link_signal(a, b, "temporal_alignment", rows)
    assert result is True


def test_relational_link_dispatches_functional_dependency(md):
    a = _attr("x", "INTEGER")
    b = _attr("y", "INTEGER")
    rows = [{"x": i, "y": i * 2} for i in range(10)]
    result = md.validate_relational_link_signal(a, b, "functional_dependency", rows)
    assert result is True


def test_relational_link_unknown_signal_passes_through(md):
    a = _attr("a", "STRING")
    b = _attr("b", "STRING")
    result = md.validate_relational_link_signal(a, b, "some_new_signal_type", [])
    assert result is True


def test_relational_link_dict_signal_dispatches(md):
    g_attr = _attr("tier", "ENUM_CATEGORY")
    v_attr = _attr("revenue", "FLOAT")
    rows = [{"tier": "A", "revenue": float(i)} for i in range(2)]
    signal = {"type": "grouped_distribution", "strength": 0.8}
    result = md.validate_relational_link_signal(g_attr, v_attr, signal, rows)
    assert result is False  # too few rows


# ------------------------------------------------------------------ infer_total_component_measures

def test_total_component_detects_pair(md):
    attrs = [
        _numeric_attr("total_injuries", "INTEGER", [10, 20, 30], qvst_role="MEASUREMENT"),
        _numeric_attr("pedestrian_injuries", "INTEGER", [6, 12, 18], qvst_role="MEASUREMENT"),
        _numeric_attr("cyclist_injuries", "INTEGER", [4, 8, 12], qvst_role="MEASUREMENT"),
    ]
    tc = md.infer_total_component_measures(attrs)
    assert "total_injuries" in tc["totals"]
    assert set(tc["totals"]["total_injuries"]) == {"pedestrian_injuries", "cyclist_injuries"}
    assert tc["components"]["pedestrian_injuries"] == "total_injuries"
    assert tc["components"]["cyclist_injuries"] == "total_injuries"


def test_total_component_returns_empty_when_too_few_attrs(md):
    attrs = [
        _numeric_attr("total_injuries", "INTEGER", [10, 20], qvst_role="MEASUREMENT"),
        _numeric_attr("pedestrian_injuries", "INTEGER", [10, 20], qvst_role="MEASUREMENT"),
    ]
    tc = md.infer_total_component_measures(attrs)
    assert tc == {"totals": {}, "components": {}}


def test_total_component_no_false_positive_without_hint(md):
    attrs = [
        _numeric_attr("revenue", "FLOAT", [100.0, 200.0, 300.0], qvst_role="MEASUREMENT"),
        _numeric_attr("cost", "FLOAT", [60.0, 120.0, 180.0], qvst_role="MEASUREMENT"),
        _numeric_attr("profit", "FLOAT", [40.0, 80.0, 120.0], qvst_role="MEASUREMENT"),
    ]
    tc = md.infer_total_component_measures(attrs)
    assert tc["totals"] == {}


def test_total_component_tolerates_near_match(md):
    attrs = [
        _numeric_attr("total_count", "INTEGER", [100, 200, 300], qvst_role="COUNT"),
        _numeric_attr("category_a", "INTEGER", [55, 110, 165], qvst_role="COUNT"),
        _numeric_attr("category_b", "INTEGER", [40, 80, 120], qvst_role="COUNT"),
    ]
    tc = md.infer_total_component_measures(attrs)
    # 55+40=95, 110+80=190, 165+120=285 — within 10% of 100/200/300
    assert "total_count" in tc["totals"]


# ------------------------------------------------------------------ infer_safe_aggregation_for_quantitative_vst

def test_safe_agg_component_forbids_total_and_siblings(md):
    tc = {
        "totals": {"total_inj": ["ped_inj", "cyc_inj"]},
        "components": {"ped_inj": "total_inj", "cyc_inj": "total_inj"},
    }
    attr = _numeric_attr("ped_inj", "INTEGER", [6, 12], qvst_role="MEASUREMENT")
    result = md.infer_safe_aggregation_for_quantitative_vst(attr, tc)
    assert result["can_sum"] is True
    assert result["can_avg"] is True
    assert "total_inj" in result["forbidden_combinations"]
    assert "cyc_inj" in result["forbidden_combinations"]


def test_safe_agg_total_forbids_components(md):
    tc = {
        "totals": {"total_inj": ["ped_inj", "cyc_inj"]},
        "components": {"ped_inj": "total_inj", "cyc_inj": "total_inj"},
    }
    attr = _numeric_attr("total_inj", "INTEGER", [10, 20], qvst_role="MEASUREMENT")
    result = md.infer_safe_aggregation_for_quantitative_vst(attr, tc)
    assert result["can_sum"] is True
    assert result["can_avg"] is False
    assert set(result["forbidden_combinations"]) == {"ped_inj", "cyc_inj"}


def test_safe_agg_count_no_avg(md):
    attr = _numeric_attr("event_count", "INTEGER", [1, 2, 3], qvst_role="COUNT")
    result = md.infer_safe_aggregation_for_quantitative_vst(attr, {"totals": {}, "components": {}})
    assert result["can_sum"] is True
    assert result["can_avg"] is False


def test_safe_agg_computational_no_sum(md):
    attr = _numeric_attr("conversion_rate", "PERCENTAGE", [0.1, 0.2], qvst_role="COMPUTATIONAL")
    result = md.infer_safe_aggregation_for_quantitative_vst(attr, {"totals": {}, "components": {}})
    assert result["can_sum"] is False
    assert result["can_avg"] is True


def test_safe_agg_returns_none_without_qvst(md):
    attr = _attr("name", "STRING")
    result = md.infer_safe_aggregation_for_quantitative_vst(attr, {"totals": {}, "components": {}})
    assert result is None


# ------------------------------------------------------------------ infer_derived_metric_candidates

def test_derived_metrics_rate_from_measurement(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1, 2, 3], qvst_role="COUNT"),
        _numeric_attr("total_injuries", "INTEGER", [10, 20, 30], qvst_role="MEASUREMENT"),
    ]
    ps = {"entity_keys": ["user_id"], "event_time": "event_date"}
    derived = md.infer_derived_metric_candidates(attrs, ps, {"totals": {}, "components": {}})
    names = [d["name"] for d in derived]
    assert any("total_injuries" in n for n in names)
    rates = [d for d in derived if d["type"] == "RATE"]
    assert rates


def test_derived_metrics_share_from_total_component(md):
    attrs = [
        _numeric_attr("total_inj", "INTEGER", [10, 20], qvst_role="MEASUREMENT"),
        _numeric_attr("ped_inj", "INTEGER", [6, 12], qvst_role="MEASUREMENT"),
        _numeric_attr("cyc_inj", "INTEGER", [4, 8], qvst_role="MEASUREMENT"),
    ]
    tc = {
        "totals": {"total_inj": ["ped_inj", "cyc_inj"]},
        "components": {"ped_inj": "total_inj", "cyc_inj": "total_inj"},
    }
    derived = md.infer_derived_metric_candidates(attrs, None, tc)
    shares = [d for d in derived if d["type"] == "RATIO"]
    assert len(shares) == 2
    share_names = {d["name"] for d in shares}
    assert "ped_inj_share" in share_names
    assert "cyc_inj_share" in share_names


def test_derived_metrics_skips_component_in_rates(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1, 2, 3], qvst_role="COUNT"),
        _numeric_attr("total_inj", "INTEGER", [10, 20, 30], qvst_role="MEASUREMENT"),
        _numeric_attr("ped_inj", "INTEGER", [6, 12, 18], qvst_role="MEASUREMENT"),
    ]
    tc = {"totals": {"total_inj": ["ped_inj"]}, "components": {"ped_inj": "total_inj"}}
    ps = {"entity_keys": ["user_id"], "event_time": "ts"}
    derived = md.infer_derived_metric_candidates(attrs, ps, tc)
    rate_numerators = {d["numerator"] for d in derived if d["type"] == "RATE"}
    assert "ped_inj" not in rate_numerators


def test_derived_metrics_falls_back_to_identifier_attrs(md):
    attrs = [
        {
            "name": "user_id",
            "properties": {
                "value_semantics": {"semantic_type": "INTEGER", "is_identifier": True},
                "stats": {"sample_values": [1, 2, 3]},
                "quantitative_vst": {"role": "COUNT"},
            },
        },
        _numeric_attr("revenue", "FLOAT", [100.0, 200.0], qvst_role="MEASUREMENT"),
    ]
    derived = md.infer_derived_metric_candidates(attrs, None, {"totals": {}, "components": {}})
    rates = [d for d in derived if d["type"] == "RATE"]
    assert rates


# ------------------------------------------------------------------ infer_process_mode

def test_process_mode_sequence_event(md):
    ps = {"signals": {"identifier_repetition": 0.6, "temporal_density": 0.2, "event_measure_presence": 0.15}}
    assert md.infer_process_mode(ps) == "SEQUENCE_EVENT"


def test_process_mode_repeated_event(md):
    ps = {"signals": {"identifier_repetition": 0.0, "temporal_density": 0.4, "event_measure_presence": 0.15}}
    assert md.infer_process_mode(ps) == "REPEATED_EVENT"


def test_process_mode_atomic_event(md):
    ps = {"signals": {"identifier_repetition": 0.0, "temporal_density": 0.2, "event_measure_presence": 0.15}}
    assert md.infer_process_mode(ps) == "ATOMIC_EVENT"


def test_process_mode_none_on_none_input(md):
    assert md.infer_process_mode(None) is None


# ------------------------------------------------------------------ get_process_numeric_measures / get_state_variable_candidates

def _make_process_attrs():
    return [
        _numeric_attr("user_id", "INTEGER", [1, 2, 3]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("revenue", "FLOAT", [100.0], qvst_role="MEASUREMENT"),
        _numeric_attr("score", "INTEGER", [5, 6, 7], process_vst_role="STATE_VARIABLE"),
    ]


def test_get_process_numeric_measures_excludes_keys_and_time(md):
    attrs = _make_process_attrs()
    ps = {"entity_keys": ["user_id"], "event_time": "event_date"}
    measures = md.get_process_numeric_measures(attrs, ps)
    names = {a["name"] for a in measures}
    assert "user_id" not in names
    assert "event_date" not in names
    assert "revenue" in names


def test_get_state_variable_candidates(md):
    attrs = _make_process_attrs()
    ps = {"entity_keys": ["user_id"], "event_time": "event_date"}
    state_vars = md.get_state_variable_candidates(attrs, ps)
    names = {a["name"] for a in state_vars}
    assert "score" in names
    assert "revenue" not in names


# ------------------------------------------------------------------ infer_time_grain_candidates

def test_time_grain_daily_data(md):
    import numpy as np
    rows = [{"ts": str(np.datetime64("2024-01-01") + np.timedelta64(i, "D"))} for i in range(30)]
    grains = md.infer_time_grain_candidates("ts", rows)
    assert "daily" in grains


def test_time_grain_weekly_data(md):
    import numpy as np
    rows = [{"ts": str(np.datetime64("2024-01-01") + np.timedelta64(i * 7, "D"))} for i in range(15)]
    grains = md.infer_time_grain_candidates("ts", rows)
    assert "weekly" in grains


def test_time_grain_monthly_data(md):
    import numpy as np
    rows = [{"ts": str(np.datetime64("2024-01-01") + np.timedelta64(i * 30, "D"))} for i in range(15)]
    grains = md.infer_time_grain_candidates("ts", rows)
    assert "monthly" in grains


def test_time_grain_returns_empty_for_few_rows(md):
    grains = md.infer_time_grain_candidates("ts", [{"ts": "2024-01-01"}] * 5)
    assert grains == []


# ------------------------------------------------------------------ infer_process_operator_semantics

def _make_ps(event_mode="SEQUENCE_EVENT"):
    return {
        "entity_keys": ["user_id"],
        "event_time": "event_date",
        "event_mode": event_mode,
    }


def test_process_operators_aggregate_over_time(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("revenue", "FLOAT", [100.0], qvst_role="MEASUREMENT"),
    ]
    ops = md.infer_process_operator_semantics(attrs, _make_ps())
    op_types = {o["operator"] for o in ops}
    assert "AGGREGATE_OVER_TIME" in op_types


def test_process_operators_change_detection_for_sequence(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("revenue", "FLOAT", [100.0], qvst_role="MEASUREMENT"),
    ]
    ops = md.infer_process_operator_semantics(attrs, _make_ps(event_mode="SEQUENCE_EVENT"))
    op_types = {o["operator"] for o in ops}
    assert "CHANGE_DETECTION" in op_types


def test_process_operators_no_change_detection_for_atomic(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("revenue", "FLOAT", [100.0], qvst_role="MEASUREMENT"),
    ]
    ops = md.infer_process_operator_semantics(attrs, _make_ps(event_mode="ATOMIC_EVENT"))
    op_types = {o["operator"] for o in ops}
    assert "CHANGE_DETECTION" not in op_types


def test_process_operators_current_state(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("balance", "FLOAT", [500.0], qvst_role="MEASUREMENT", process_vst_role="STATE_VARIABLE"),
    ]
    ops = md.infer_process_operator_semantics(attrs, _make_ps())
    op_types = {o["operator"] for o in ops}
    assert "CURRENT_STATE" in op_types


def test_process_operators_normalized_rate(md):
    attrs = [
        _numeric_attr("user_id", "INTEGER", [1]),
        _numeric_attr("event_date", "DATE", []),
        _numeric_attr("event_count", "INTEGER", [3], qvst_role="COUNT"),
        _numeric_attr("revenue", "FLOAT", [100.0], qvst_role="MEASUREMENT"),
    ]
    ops = md.infer_process_operator_semantics(attrs, _make_ps())
    op_types = {o["operator"] for o in ops}
    assert "NORMALIZED_RATE" in op_types


# ------------------------------------------------------------------ infer_process_query_constraints

def test_process_constraints_time_filter(md):
    ps = {"entity_keys": ["user_id"], "event_time": "event_date", "constraints": {}}
    ops = [{"operator": "AGGREGATE_OVER_TIME", "event_time": "event_date", "measures": ["revenue"]}]
    constraints = md.infer_process_query_constraints(ops, ps)
    assert "requires_time_filter" in constraints
    assert constraints["requires_time_filter"]["field"] == "event_date"


def test_process_constraints_entity_key_filter(md):
    ps = {"entity_keys": ["user_id"], "event_time": "event_date", "constraints": {}}
    ops = [{"operator": "CHANGE_DETECTION", "entity_keys": ["user_id"], "event_time": "event_date", "measures": []}]
    constraints = md.infer_process_query_constraints(ops, ps)
    assert "requires_entity_key_filter" in constraints


def test_process_constraints_latest_record_only(md):
    ps = {"entity_keys": ["user_id"], "event_time": "event_date", "constraints": {}}
    ops = [{"operator": "CURRENT_STATE", "entity_keys": ["user_id"], "state_variables": ["balance"], "event_time": "event_date"}]
    constraints = md.infer_process_query_constraints(ops, ps)
    assert "latest_record_only" in constraints


def test_process_constraints_no_row_local_substitution(md):
    ps = {"entity_keys": [], "event_time": None, "constraints": {"requires_aggregation": True}}
    constraints = md.infer_process_query_constraints([], ps)
    assert constraints.get("no_row_local_substitution") is True


def test_process_constraints_empty_for_no_operators(md):
    ps = {"entity_keys": [], "event_time": None, "constraints": {}}
    constraints = md.infer_process_query_constraints([], ps)
    assert constraints == {}


# ------------------------------------------------------------------ infer_role_query_constraints

def test_role_constraints_identifier(md):
    attrs = [_numeric_attr("user_id", "INTEGER", [1, 2], semantic_role="IDENTIFIER")]
    con = md.infer_role_query_constraints(attrs, [])
    assert con["user_id"]["can_group_by"] is True
    assert con["user_id"]["should_not_aggregate"] is True


def test_role_constraints_segmentation_driver(md):
    attrs = [_numeric_attr("category", "ENUM_CATEGORY", [], semantic_role="SEGMENTATION_DRIVER")]
    con = md.infer_role_query_constraints(attrs, [])
    assert con["category"]["can_group_by"] is True


def test_role_constraints_event_time(md):
    attrs = [_numeric_attr("event_date", "DATE", [], semantic_role="EVENT_TIME")]
    con = md.infer_role_query_constraints(attrs, [])
    assert con["event_date"]["can_order_by"] is True
    assert con["event_date"]["can_filter"] is True


def test_role_constraints_propagates_forbidden_combinations(md):
    attrs = [
        _numeric_attr(
            "total_inj", "INTEGER", [10],
            qvst_role="MEASUREMENT",
            safe_agg={"can_sum": True, "can_avg": False, "forbidden_combinations": ["ped_inj", "cyc_inj"], "notes": []},
            semantic_role="EVIDENCE",
        )
    ]
    con = md.infer_role_query_constraints(attrs, [])
    assert con["total_inj"]["forbidden_combinations"] == ["ped_inj", "cyc_inj"]


def test_role_constraints_should_not_sum_for_computational(md):
    attrs = [
        _numeric_attr(
            "conversion_rate", "PERCENTAGE", [0.1],
            qvst_role="COMPUTATIONAL",
            safe_agg={"can_sum": False, "can_avg": True, "forbidden_combinations": [], "notes": []},
            semantic_role="EVIDENCE",
        )
    ]
    con = md.infer_role_query_constraints(attrs, [])
    assert con["conversion_rate"]["should_not_sum"] is True


def test_role_constraints_empty_for_descriptive_no_safe_agg(md):
    attrs = [_numeric_attr("notes", "FREE_TEXT", [], semantic_role="DESCRIPTIVE")]
    con = md.infer_role_query_constraints(attrs, [])
    assert "notes" not in con


def test_temporal_density_signal_yyyymm_does_not_crash(md):
    # YYYYMM values (e.g. "201112") were previously parsed as year 201112
    # (datetime64[Y]), causing a TypeError when dividing by timedelta64[D].
    rows = [{"date": str(201101 + i)} for i in range(20)]
    result = md.temporal_density_signal("date", rows)
    assert isinstance(result, float)


def test_temporal_density_signal_yyyymm_monthly_cadence(md):
    # 12 consecutive months should be detected as monthly (>= 30-day avg → 0.2).
    rows = [{"date": f"{2020 + i // 12}{(i % 12) + 1:02d}"} for i in range(15)]
    result = md.temporal_density_signal("date", rows)
    assert result in (0.0, 0.2, 0.4)


# ------------------------------------------------------------------ parse_timestamp

def test_parse_timestamp_yyyymm():
    import numpy as np
    assert parse_timestamp("201112") == np.datetime64("2011-12-01")
    assert parse_timestamp(201112) == np.datetime64("2011-12-01")
    assert parse_timestamp(" 201112 ") == np.datetime64("2011-12-01")


def test_parse_timestamp_yyyymmdd():
    import numpy as np
    assert parse_timestamp("20111215") == np.datetime64("2011-12-15")


def test_parse_timestamp_bare_year_pinned_to_period_start():
    import numpy as np
    assert parse_timestamp("2011") == np.datetime64("2011-01-01")
    assert parse_timestamp("2011-12") == np.datetime64("2011-12-01")


def test_parse_timestamp_preserves_sub_day_resolution():
    import numpy as np
    assert parse_timestamp("2011-12-01T10:30:00") == np.datetime64("2011-12-01T10:30:00")


def test_parse_timestamp_rejects_unparseable():
    # Digit runs of an implausible length would otherwise become absurd years
    # (np.datetime64("999999") is the year 999999).
    assert parse_timestamp("999999") is None
    assert parse_timestamp("12345") is None
    assert parse_timestamp("not-a-date") is None
    assert parse_timestamp("") is None
    assert parse_timestamp(None) is None


def test_parse_timestamp_result_divides_by_days():
    # The whole point: every returned value must survive a day-resolution delta.
    import numpy as np
    a, b = parse_timestamp("201111"), parse_timestamp("201112")
    assert float((b - a) / np.timedelta64(1, "D")) == 30.0


# ------------------------------------------------------------------ YYYYMM handling across callers

def _yearmonth_rows(key="date", n=15, start_year=2011):
    return [{key: f"{start_year + i // 12}{(i % 12) + 1:02d}"} for i in range(n)]


def test_time_grain_candidates_yyyymm(md):
    # Same TypeError as #67, via infer_time_grain_candidates.
    grains = md.infer_time_grain_candidates("date", _yearmonth_rows())
    assert "monthly" in grains


def test_time_grain_candidates_integer_yyyymm(md):
    # SQLite stores such columns as INTEGER just as often as TEXT.
    rows = [{"date": int(r["date"])} for r in _yearmonth_rows()]
    assert "monthly" in md.infer_time_grain_candidates("date", rows)


def test_process_patterns_yyyymm(md):
    rows = []
    for user in range(4):
        for row in _yearmonth_rows(n=6):
            rows.append({"user_id": user, **row})
    ps = {"entity_keys": ["user_id"], "event_time": "date"}
    patterns = md.infer_process_patterns("yearmonth", _make_process_attrs(), rows, ps)
    assert patterns is not None
    assert patterns["cadence"] == "monthly"


def test_temporal_trends_yyyymm(md):
    rows = [{**row, "revenue": float(i)} for i, row in enumerate(_yearmonth_rows())]
    attrs = [_numeric_attr("revenue", "FLOAT", [1.0])]
    ps = {"entity_keys": ["user_id"], "event_time": "date"}
    trends = md.infer_temporal_trends(attrs, rows, ps)
    assert trends is not None
    assert trends["trends"][0]["trend_direction"] == "increasing"


def test_temporal_trends_skips_rows_with_non_numeric_measure(md):
    # A non-numeric measure used to append the timestamp before float() raised,
    # leaving t_vals and v_vals misaligned for every later row.
    rows = [{**row, "revenue": float(i)} for i, row in enumerate(_yearmonth_rows(n=14))]
    rows.insert(3, {"date": "201204", "revenue": "n/a"})
    attrs = [_numeric_attr("revenue", "FLOAT", [1.0])]
    ps = {"entity_keys": ["user_id"], "event_time": "date"}
    trends = md.infer_temporal_trends(attrs, rows, ps)
    assert trends is not None
    assert trends["trends"][0]["trend_direction"] == "increasing"
