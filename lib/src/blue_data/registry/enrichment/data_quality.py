"""Deterministic data quality metrics from attribute stats and semantic type.

All functions are pure (no I/O) and operate on already-collected data so they
can run offline after ``collect_source_stats``.

Tier 1 — raw counts only (always available):
    missing_value_rate, fill_rate, is_partial_attribute, cardinality_ratio

Tier 2 — sample_values + semantic type (deterministic):
    disguised_missing_rate, format_violation_rate, heterogeneous_format_rate

Tier 3 — most_common_vals with frequencies (requires extended stats):
    rare_value_rate, suspected_typo_rate

Entity-level:
    duplicate_row_rate, effective_noise_rate, columns_with_error_rate, dominant_error_type
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

# ---------------------------------------------------------------------------
# Sentinel vocabulary for disguised missing values
# ---------------------------------------------------------------------------

_DISGUISED_SENTINELS: frozenset[str] = frozenset({
    "", "n/a", "na", "n.a", "n.a.", "null", "none", "nan", "-", "--", ".",
    "..", "?", "??", "-9999", "-999", "0000", "00/00/0000", "tbd", "tba",
    "pending", "unknown", "missing", "not available", "not applicable",
    "not provided", "<empty>", "<null>", "<none>", "<missing>", "undefined",
})


# ---------------------------------------------------------------------------
# Format validators keyed by semantic type
# ---------------------------------------------------------------------------

_DATE_RE      = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?", re.I)
_UUID_RE      = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_EMAIL_RE     = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE       = re.compile(r"^https?://\S+$", re.I)
_PHONE_RE     = re.compile(r"^[\+\d][\d\s\-\(\)\.]{6,}$")
_ISO2_RE      = re.compile(r"^[A-Z]{2}$")
_ISO3_RE      = re.compile(r"^[A-Z]{3}$")
_ZIP_RE       = re.compile(r"^\d{5}(-\d{4})?$")
_HASH_RE      = re.compile(r"^[0-9a-f]{32,}$", re.I)

_FORMAT_VALIDATORS: dict[str, re.Pattern] = {
    "DATE":                _DATE_RE,
    "DATETIME":            _DATETIME_RE,
    "UUID":                _UUID_RE,
    "EMAIL":               _EMAIL_RE,
    "URL":                 _URL_RE,
    "PHONE_NUMBER":        _PHONE_RE,
    "COUNTRY_CODE_ISO2":   _ISO2_RE,
    "COUNTRY_CODE_ISO3":   _ISO3_RE,
    "POSTAL_CODE":         _ZIP_RE,
    "HASH":                _HASH_RE,
}

# Date format patterns for heterogeneous_format_rate (name → regex)
_DATE_FORMAT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ISO",      re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("US",       re.compile(r"^\d{2}/\d{2}/\d{4}$")),
    ("EU_dash",  re.compile(r"^\d{2}-\d{2}-\d{4}$")),
    ("ISO_slash",re.compile(r"^\d{4}/\d{2}/\d{2}$")),
    ("EU_dot",   re.compile(r"^\d{2}\.\d{2}\.\d{4}$")),
]


# ---------------------------------------------------------------------------
# Tier 2 helpers
# ---------------------------------------------------------------------------

def _disguised_missing_rate(sample_values: list[str]) -> float:
    if not sample_values:
        return 0.0
    hits = sum(1 for v in sample_values if v.strip().lower() in _DISGUISED_SENTINELS)
    return round(hits / len(sample_values), 4)


def _format_violation_rate(sample_values: list[str], semantic_type: str) -> float:
    pattern = _FORMAT_VALIDATORS.get(semantic_type)
    if pattern is None:
        return 0.0
    violations = sum(1 for v in sample_values if v and not pattern.match(v.strip()))
    return round(violations / len(sample_values), 4) if sample_values else 0.0


def _heterogeneous_format_rate(sample_values: list[str], semantic_type: str) -> float:
    """Fraction of values using a minority date/datetime format within the column."""
    if semantic_type not in ("DATE", "DATETIME") or not sample_values:
        return 0.0
    fmt_counts: Counter = Counter()
    for v in sample_values:
        for name, pat in _DATE_FORMAT_PATTERNS:
            if pat.match(v.strip()):
                fmt_counts[name] += 1
                break
        else:
            fmt_counts["other"] += 1
    if len(fmt_counts) <= 1:
        return 0.0
    majority = max(fmt_counts.values())
    minority = len(sample_values) - majority
    return round(minority / len(sample_values), 4)


# ---------------------------------------------------------------------------
# Tier 3 helpers
# ---------------------------------------------------------------------------

def _edit_distance(a: str, b: str) -> int:
    """Iterative Levenshtein with early exit when gap > 2."""
    if abs(len(a) - len(b)) > 2:
        return 3
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def _rare_value_rate(most_common_vals: list[tuple[Any, int]]) -> float:
    """Fraction of distinct values that appear exactly once (hapax legomena)."""
    if not most_common_vals:
        return 0.0
    singletons = sum(1 for _, cnt in most_common_vals if cnt == 1)
    return round(singletons / len(most_common_vals), 4)


def _suspected_typo_rate(most_common_vals: list[tuple[Any, int]]) -> float:
    """Fraction of distinct values that are rare AND edit-distance ≤ 2 from a frequent value."""
    if not most_common_vals:
        return 0.0
    rare     = [str(v) for v, cnt in most_common_vals if cnt == 1]
    frequent = [str(v) for v, cnt in most_common_vals if cnt > 1]
    if not rare or not frequent:
        return 0.0
    suspected = sum(
        1 for r in rare
        if any(_edit_distance(r.lower(), f.lower()) <= 2 for f in frequent)
    )
    return round(suspected / len(most_common_vals), 4)


# ---------------------------------------------------------------------------
# Public API — attribute-level
# ---------------------------------------------------------------------------

def compute_attribute_dq(
    stats: dict,
    value_semantics: dict | None = None,
    partial_threshold: float = 0.5,
) -> dict:
    """Compute data quality metrics for one attribute from its collected stats.

    Args:
        stats:             Output of ``fetch_property_stats`` (count, null_count,
                           distinct_count, sample_values, most_common_vals, …).
        value_semantics:   Output of ``SemanticTypeInferencer.infer`` stored as the
                           ``value_semantics`` property (used for format checks).
        partial_threshold: ``missing_value_rate`` above this sets ``is_partial_attribute``.

    Returns:
        Flat dict suitable for storage as the ``"data_quality"`` property.
    """
    count        = int(stats.get("count") or 0)
    null_count   = int(stats.get("null_count") or 0)
    distinct     = int(stats.get("distinct_count") or 0)
    total        = count + null_count
    samples: list[str] = [str(v) for v in (stats.get("sample_values") or []) if v is not None]
    most_common: list[tuple[Any, int]] = stats.get("most_common_vals") or []
    sem_type: str = (value_semantics or {}).get("semantic_type", "UNKNOWN")

    # --- Tier 1 ---
    missing_rate = round(null_count / total, 4) if total else 0.0
    result: dict = {
        "missing_value_rate":   missing_rate,
        "fill_rate":            round(1.0 - missing_rate, 4),
        "is_partial_attribute": missing_rate > partial_threshold,
        "cardinality_ratio":    round(distinct / count, 4) if count else 0.0,
    }

    # --- Tier 2 ---
    result["disguised_missing_rate"]    = _disguised_missing_rate(samples)
    result["format_violation_rate"]     = _format_violation_rate(samples, sem_type)
    result["heterogeneous_format_rate"] = _heterogeneous_format_rate(samples, sem_type)

    # --- Tier 3 ---
    # Typo detection only makes sense for string-typed columns. Two guards:
    # (1) semantic type must be string-like (not DATE, UUID, FLOAT, …)
    # (2) values must not all be numeric — catches UNKNOWN columns whose stats
    #     reveal they are actually numeric (no semantic enrichment yet).
    def _all_numeric(vals) -> bool:
        return bool(vals) and all(isinstance(v, (int, float)) for v, _ in vals)

    typo_applicable = sem_type in _STRING_SEMANTIC_TYPES and not _all_numeric(most_common)
    if most_common:
        result["rare_value_rate"]     = _rare_value_rate(most_common)
        result["suspected_typo_rate"] = _suspected_typo_rate(most_common) if typo_applicable else None
    else:
        result["rare_value_rate"]     = None
        result["suspected_typo_rate"] = None

    return result


# ---------------------------------------------------------------------------
# Public API — entity-level
# ---------------------------------------------------------------------------

_NOISE_KEYS = (
    "missing_value_rate",
    "disguised_missing_rate",
    "format_violation_rate",
    "suspected_typo_rate",
)

# Semantic types where edit-distance typo detection is meaningful
_STRING_SEMANTIC_TYPES: frozenset[str] = frozenset({
    "STRING", "FREE_TEXT", "ENUM_CATEGORY", "TEXT_CATEGORY", "TAG", "LABEL",
    "PERSON_NAME", "ORG_NAME", "JOB_TITLE", "SKILL_TERM", "CONTROLLED_TERM",
    "CITY_NAME", "ADDRESS_FREEFORM", "DEMOGRAPHIC_TERM", "UNKNOWN",
})


def compute_entity_dq_summary(
    attribute_dq: dict[str, dict],
    row_samples: list[dict] | None = None,
) -> dict:
    """Aggregate per-attribute DQ dicts into an entity-level summary.

    Args:
        attribute_dq:  ``{attribute_name: data_quality_dict}`` for every attribute
                       that has a ``data_quality`` property.
        row_samples:   Entity row samples (from entity ``stats``), used to compute
                       ``duplicate_row_rate`` via hash-based deduplication.

    Returns:
        Flat dict suitable for storage as the ``"data_quality_summary"`` property.
    """
    if not attribute_dq:
        return {}

    # effective_noise_rate — mean of all non-None noise values across attributes
    noise_vals = [
        v for dq in attribute_dq.values()
        for k in _NOISE_KEYS
        if (v := dq.get(k)) is not None
    ]
    effective_noise = round(sum(noise_vals) / len(noise_vals), 4) if noise_vals else 0.0

    # columns with at least one metric > 1%
    cols_with_errors = [
        attr for attr, dq in attribute_dq.items()
        if any((dq.get(k) or 0) > 0.01 for k in _NOISE_KEYS)
    ]

    # dominant error type — which noise key has the highest total across attributes
    type_totals: dict[str, float] = {}
    for dq in attribute_dq.values():
        for k in _NOISE_KEYS:
            v = dq.get(k) or 0.0
            type_totals[k] = type_totals.get(k, 0.0) + v
    dominant = max(type_totals, key=type_totals.get) if type_totals else None

    # duplicate_row_rate from row_samples
    dup_rate: float | None = None
    if row_samples:
        row_hashes = [hash(tuple(sorted(str(v) for v in row.values()))) for row in row_samples]
        n_dupes = len(row_hashes) - len(set(row_hashes))
        dup_rate = round(n_dupes / len(row_hashes), 4)

    return {
        "effective_noise_rate":    effective_noise,
        "columns_with_errors":     cols_with_errors,
        "columns_with_error_rate": round(len(cols_with_errors) / len(attribute_dq), 4),
        "dominant_error_type":     dominant,
        "duplicate_row_rate":      dup_rate,
    }
