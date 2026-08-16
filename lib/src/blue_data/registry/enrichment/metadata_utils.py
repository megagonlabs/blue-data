"""Pure utility functions for the MetaData enrichment pipeline.

All functions here are stateless — they take only plain dicts, lists, and
scalars. No registry, LLM, or taxonomy access.
"""
from __future__ import annotations

import math
from typing import Any


# ------------------------------------------------------------------
# Math helpers
# ------------------------------------------------------------------

def mean_safe(vals: list) -> float | None:
    return sum(vals) / len(vals) if vals else None


def safe_pearson(x: list, y: list) -> float:
    if len(x) < 5 or len(y) < 5:
        return 0.0
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denx = math.sqrt(sum((a - mx) ** 2 for a in x))
    deny = math.sqrt(sum((b - my) ** 2 for b in y))
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


def get_numeric_samples(attr: dict) -> list[float]:
    stats = attr.get("properties", {}).get("stats", {})
    nums = []
    for v in stats.get("sample_values", []):
        try:
            nums.append(float(v))
        except Exception:
            pass
    return nums


# ------------------------------------------------------------------
# Signal helpers
# ------------------------------------------------------------------

def has_row_cooccurrence(a: dict, b: dict, row_samples: list, min_rows: int = 5) -> bool:
    a_name, b_name = a["name"], b["name"]
    count = 0
    for row in row_samples:
        if row.get(a_name) is not None and row.get(b_name) is not None:
            count += 1
            if count >= min_rows:
                return True
    return False


def functional_dependency_signal(a: dict, b: dict) -> bool:
    a_vals = get_numeric_samples(a)
    b_vals = get_numeric_samples(b)
    if len(a_vals) < 5 or len(b_vals) < 5:
        return False
    return abs(safe_pearson(a_vals, b_vals)) > 0.7


def temporal_alignment_signal(a: dict, b: dict) -> bool:
    temporal = {"DATE", "DATETIME", "TIME", "DURATION"}
    a_type = a.get("properties", {}).get("value_semantics", {}).get("semantic_type")
    b_type = b.get("properties", {}).get("value_semantics", {}).get("semantic_type")
    return a_type in temporal and b_type not in temporal


def grouped_distribution_signal(group_attr: dict, value_attr: dict) -> bool:
    g_vals = group_attr.get("properties", {}).get("stats", {}).get("sample_values", [])
    v_vals = value_attr.get("properties", {}).get("stats", {}).get("sample_values", [])
    if not g_vals or not v_vals:
        return False
    try:
        groups: dict[Any, list] = {}
        for g, v in zip(g_vals, v_vals):
            try:
                v = float(v)
            except Exception:
                continue
            groups.setdefault(g, []).append(v)

        if len(groups) < 2:
            return False
        if sum(1 for vals in groups.values() if len(vals) >= 2) < 2:
            return False

        means = [sum(vals) / len(vals) for vals in groups.values()]
        max_mean = max(abs(m) for m in means) if means else 0.0
        if max_mean == 0:
            return False

        spread = max(means) - min(means)
        avg_mean = sum(abs(m) for m in means) / len(means)
        relative_spread = spread / avg_mean if avg_mean > 0 else 0.0
        return spread > 0.12 * max_mean or relative_spread > 0.18
    except Exception:
        return False


def grouped_distribution_signal_row_aligned(
    group_attr: dict, value_attr: dict, row_samples: list
) -> bool:
    g_name, v_name = group_attr["name"], value_attr["name"]
    g_vals, v_vals = [], []
    for row in row_samples:
        g = row.get(g_name)
        v = row.get(v_name)
        if g is None or v is None:
            continue
        try:
            v_vals.append(float(v))
            g_vals.append(g)
        except Exception:
            pass
    if len(g_vals) < 5:
        return False
    return grouped_distribution_signal(
        {"properties": {"stats": {"sample_values": g_vals}}},
        {"properties": {"stats": {"sample_values": v_vals}}},
    )


def is_sparse_count_axis(attr: dict, values: list) -> bool:
    if not values:
        return False
    vsi = attr.get("properties", {}).get("value_semantics", {})
    if vsi.get("semantic_type") not in {"INTEGER", "NUMERIC_GENERAL"}:
        return False
    name = attr.get("name", "").lower()
    if name in {"latitude", "longitude", "lat", "lon", "lng"}:
        return False
    if not vsi.get("numeric", {}).get("is_discrete", True):
        return False
    n = len(values)
    zero_frac = sum(v == 0 for v in values) / n
    max_val = max(values)
    distinct = len(set(values))
    if zero_frac >= 0.7 and distinct <= 10:
        return True
    if zero_frac >= 0.4 and max_val >= 5:
        return True
    return False


def infer_tail_threshold(values: list) -> int | None:
    values = sorted(values)
    n = len(values)
    non_zero = [v for v in values if v > 0]
    if not non_zero:
        return None
    if max(non_zero) <= 3:
        return 1
    for t in [5, 10, 15, 20]:
        if sum(v >= t for v in values) / n < 0.01:
            return t
    return max(values)


# ------------------------------------------------------------------
# Context builder
# ------------------------------------------------------------------

def build_attribute_context(attributes: list, target_attr_name: str) -> dict:
    context: dict = {
        "sibling_attributes": [],
        "numeric_distributions": {},
        "temporal_hints": [],
        "co_occurrence_hints": [],
        "relative_behavior": [],
    }
    for attr in attributes:
        name = attr.get("name")
        if name == target_attr_name:
            continue
        props = attr.get("properties", {}) or {}
        stats = props.get("stats", {}) or {}
        sem = props.get("value_semantics", {}) or {}
        samples = stats.get("sample_values", [])[:5]

        context["sibling_attributes"].append(name)

        min_val, max_val = stats.get("min"), stats.get("max")
        is_numeric = isinstance(min_val, (int, float)) or isinstance(max_val, (int, float))
        if is_numeric:
            context["numeric_distributions"][name] = {
                "min": min_val,
                "max": max_val,
                "distinct": stats.get("distinct_count"),
            }
            if not sem.get("is_identifier") and isinstance(max_val, (int, float)):
                context["relative_behavior"].append({
                    "attribute": name,
                    "scale_hint": (
                        "small_range" if max_val < 100
                        else "medium_range" if max_val < 10000
                        else "large_range"
                    ),
                })

        if sem.get("semantic_type") in ("DATE", "DATETIME", "DURATION"):
            context["temporal_hints"].append(name)

        if samples:
            context["co_occurrence_hints"].append({"attribute": name, "sample_values": samples})

    if len(context["relative_behavior"]) >= 2:
        context["relative_behavior_summary"] = {
            "comparison": [(rb["attribute"], rb["scale_hint"]) for rb in context["relative_behavior"]]
        }
    return context
