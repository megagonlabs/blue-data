"""Deterministic data quality metrics from attribute stats and semantic type.

All functions are pure (no I/O) and operate on already-collected data so they
can run offline after ``collect_source_stats``.

Tier 1 — raw counts only (always available):
    missing_value_rate, fill_rate, is_partial_attribute, cardinality_ratio

Tier 2 — sample_values + semantic type (deterministic):
    disguised_missing_rate, format_violation_rate, heterogeneous_format_rate,
    embedded_value_rate

Tier 3 — most_common_vals with frequencies (requires extended stats):
    rare_value_rate, suspected_typo_rate, representation_fragmentation_rate,
    outlier_rate (also requires mean + variance from extended stats)

Tier 4 — derived repairability (no extra data needed):
    repairability.{deterministic, ambiguous, unrecoverable}

Entity-level:
    duplicate_row_rate, rows_with_error_rate, multi_error_row_rate,
    effective_noise_rate, columns_with_error_rate, dominant_error_type,
    worst_attribute, misplaced_value_rate (per-attribute breakdown)
"""
from __future__ import annotations

import math
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
    "DATE":              _DATE_RE,
    "DATETIME":          _DATETIME_RE,
    "UUID":              _UUID_RE,
    "EMAIL":             _EMAIL_RE,
    "URL":               _URL_RE,
    "PHONE_NUMBER":      _PHONE_RE,
    "COUNTRY_CODE_ISO2": _ISO2_RE,
    "COUNTRY_CODE_ISO3": _ISO3_RE,
    "POSTAL_CODE":       _ZIP_RE,
    "HASH":              _HASH_RE,
}

# Date format patterns for heterogeneous_format_rate
_DATE_FORMAT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ISO",      re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("US",       re.compile(r"^\d{2}/\d{2}/\d{4}$")),
    ("EU_dash",  re.compile(r"^\d{2}-\d{2}-\d{4}$")),
    ("ISO_slash",re.compile(r"^\d{4}/\d{2}/\d{2}$")),
    ("EU_dot",   re.compile(r"^\d{2}\.\d{2}\.\d{4}$")),
]

# Semantic types where edit-distance typo and fragmentation detection are meaningful
_STRING_SEMANTIC_TYPES: frozenset[str] = frozenset({
    "STRING", "FREE_TEXT", "ENUM_CATEGORY", "TEXT_CATEGORY", "TAG", "LABEL",
    "PERSON_NAME", "ORG_NAME", "JOB_TITLE", "SKILL_TERM", "CONTROLLED_TERM",
    "CITY_NAME", "ADDRESS_FREEFORM", "DEMOGRAPHIC_TERM", "UNKNOWN",
})

# Patterns that suggest a value embeds a structured fact inside free text
_EMBEDDED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\w+\s+in\s+\w+", re.I),         # "Incident in Travis County"
    re.compile(r"\w+[,;]\s*\w+[,;]\s*\w+"),         # comma/semicolon multi-part
    re.compile(r"^\w[\w\s]+:\s*\w"),                 # "Key: value" at start
    re.compile(r"\s{2,}"),                           # multiple spaces (tabular)
]
_EMBEDDED_MIN_LEN = 25


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
    return round((len(sample_values) - majority) / len(sample_values), 4)


def _embedded_value_rate(sample_values: list[str], semantic_type: str) -> float:
    """Fraction of values that embed a structured fact inside free text.

    Skipped for FREE_TEXT/UNKNOWN where long values are expected; only meaningful
    for columns with a structured semantic type (dates, names, codes, etc.).
    """
    if not sample_values or semantic_type in ("FREE_TEXT", "UNKNOWN", "STRING"):
        return 0.0
    embedded = sum(
        1 for v in sample_values
        if len(v) >= _EMBEDDED_MIN_LEN and any(p.search(v) for p in _EMBEDDED_PATTERNS)
    )
    return round(embedded / len(sample_values), 4)


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
    if not most_common_vals:
        return 0.0
    singletons = sum(1 for _, cnt in most_common_vals if cnt == 1)
    return round(singletons / len(most_common_vals), 4)


def _suspected_typo_rate(most_common_vals: list[tuple[Any, int]]) -> float:
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


def _representation_fragmentation_rate(most_common_vals: list[tuple[Any, int]]) -> float:
    """Fraction of distinct values that appear to be variant representations of another value.

    Detects abbreviations (initials or short prefix) and case-normalised duplicates.
    Conservative: only flags clear structural patterns to keep false-positive rate low.
    """
    if not most_common_vals:
        return 0.0
    vals = [str(v) for v, _ in most_common_vals if v is not None]
    if len(vals) <= 1:
        return 0.0

    def _is_abbreviation(short: str, long: str) -> bool:
        s, lo = short.strip(), long.strip()
        if not s or not lo:
            return False
        # Initials: "NYC" == first letter of each word in "New York City"
        words = lo.split()
        if (len(s) == len(words) and len(s) >= 2
                and s.upper() == "".join(w[0].upper() for w in words if w)):
            return True
        # Short prefix: "US" is a prefix of "United States" (≤5 chars, unambiguous)
        if len(s) <= 5 and lo.lower().startswith(s.lower() + " "):
            return True
        return False

    fragmented: set[str] = set()
    for i, a in enumerate(vals):
        for b in vals:
            if a == b:
                continue
            short, long = (a, b) if len(a) < len(b) else (b, a)
            if _is_abbreviation(short, long):
                fragmented.add(a)
                fragmented.add(b)
                break

    return round(len(fragmented) / len(vals), 4)


def _outlier_rate(
    mean: float | None,
    variance: float | None,
    most_common_vals: list[tuple[Any, int]],
    z_threshold: float = 3.0,
) -> float | None:
    """Fraction of values (by row count) that are > z_threshold standard deviations from the mean.

    Returns None when mean/variance are unavailable or the column is non-numeric.
    """
    if mean is None or variance is None or variance <= 0:
        return None
    numeric_vals = [(v, cnt) for v, cnt in most_common_vals if isinstance(v, (int, float))]
    if not numeric_vals:
        return None
    std = math.sqrt(variance)
    total = sum(cnt for _, cnt in numeric_vals)
    outliers = sum(cnt for v, cnt in numeric_vals if abs(v - mean) > z_threshold * std)
    return round(outliers / total, 4) if total else None


# ---------------------------------------------------------------------------
# Tier 4 — repairability (derived, no extra data)
# ---------------------------------------------------------------------------

def _compute_repairability(dq: dict) -> dict:
    """Approximate repairability breakdown from per-attribute DQ metrics.

    Deterministic: errors with a rule-based fix (format normalization, sentinel
    replacement, single nearest-neighbour typo correction).

    Ambiguous: errors that require inference or context (disguised domain-specific
    sentinels, typos with multiple plausible corrections, representation variants).

    Unrecoverable: true nulls where the original value is gone.
    """
    fmt       = dq.get("format_violation_rate") or 0.0
    disguised = dq.get("disguised_missing_rate") or 0.0
    typo      = dq.get("suspected_typo_rate") or 0.0
    frag      = dq.get("representation_fragmentation_rate") or 0.0
    missing   = dq.get("missing_value_rate") or 0.0

    # ~60% of disguised values are universal sentinels (N/A, NULL, -) — auto-replaceable
    # ~40% are domain-specific (TBD, pending) — need human review
    deterministic = round(min(fmt + disguised * 0.6, 1.0), 4)
    ambiguous     = round(min(typo + frag + disguised * 0.4, 1.0), 4)
    unrecoverable = round(missing, 4)

    return {
        "deterministic":  deterministic,
        "ambiguous":      ambiguous,
        "unrecoverable":  unrecoverable,
    }


# ---------------------------------------------------------------------------
# Entity-level cross-column helpers
# ---------------------------------------------------------------------------

def compute_misplaced_rates(
    attribute_stats: dict[str, dict],
    attribute_semantics: dict[str, dict],
) -> dict[str, float]:
    """For each attribute, fraction of sample values whose format matches a DIFFERENT
    column's semantic type better than its own.

    Only meaningful for columns whose semantic type has a format validator (dates,
    emails, UUIDs, …). Returns 0.0 for unvalidated or string-typed columns.
    """
    sem_types = {
        attr: (attribute_semantics.get(attr) or {}).get("semantic_type", "UNKNOWN")
        for attr in attribute_stats
    }
    result: dict[str, float] = {}
    for attr, stats in attribute_stats.items():
        samples = [str(v).strip() for v in (stats.get("sample_values") or []) if v is not None]
        if not samples:
            result[attr] = 0.0
            continue
        own_type = sem_types.get(attr, "UNKNOWN")
        own_validator = _FORMAT_VALIDATORS.get(own_type)
        other_validators = [
            pat for other_attr, other_type in sem_types.items()
            if other_attr != attr
            and other_type != own_type
            and (pat := _FORMAT_VALIDATORS.get(other_type)) is not None
        ]
        if not other_validators:
            result[attr] = 0.0
            continue
        misplaced = sum(
            1 for v in samples
            if (own_validator is None or not own_validator.match(v))
            and any(pat.match(v) for pat in other_validators)
        )
        result[attr] = round(misplaced / len(samples), 4)
    return result


def compute_row_error_rates(
    row_samples: list[dict],
    attribute_semantics: dict[str, dict] | None = None,
) -> tuple[float | None, float | None]:
    """(rows_with_error_rate, multi_error_row_rate) from row_samples.

    A cell is flagged when it is null, a disguised sentinel, or violates the
    format of its column's semantic type.  Uses sample rows only, so rates are
    approximate on large tables.
    """
    if not row_samples:
        return None, None

    sem_types = {
        attr: (attribute_semantics or {}).get(attr, {}).get("semantic_type", "UNKNOWN")
        for attr in row_samples[0]
    }
    validators = {attr: _FORMAT_VALIDATORS.get(st) for attr, st in sem_types.items()}

    rows_with_error = 0
    multi_error_rows = 0
    for row in row_samples:
        error_count = 0
        for attr, value in row.items():
            if value is None:
                error_count += 1
                continue
            sv = str(value).strip()
            if sv.lower() in _DISGUISED_SENTINELS:
                error_count += 1
                continue
            pat = validators.get(attr)
            if pat and not pat.match(sv):
                error_count += 1
        if error_count >= 1:
            rows_with_error += 1
        if error_count >= 2:
            multi_error_rows += 1

    n = len(row_samples)
    return round(rows_with_error / n, 4), round(multi_error_rows / n, 4)


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
        stats:             Output of ``fetch_property_stats`` — must include
                           count, null_count, distinct_count, sample_values,
                           most_common_vals; optionally mean and variance for
                           numeric outlier detection.
        value_semantics:   ``value_semantics`` registry property (used for
                           format checks and type guards).
        partial_threshold: ``missing_value_rate`` above this sets
                           ``is_partial_attribute``.

    Returns:
        Flat dict suitable for storage as the ``"data_quality"`` property.
    """
    count      = int(stats.get("count") or 0)
    null_count = int(stats.get("null_count") or 0)
    distinct   = int(stats.get("distinct_count") or 0)
    total      = count + null_count
    samples    = [str(v) for v in (stats.get("sample_values") or []) if v is not None]
    most_common: list[tuple[Any, int]] = stats.get("most_common_vals") or []
    mean       = stats.get("mean")
    variance   = stats.get("variance")
    sem_type   = (value_semantics or {}).get("semantic_type", "UNKNOWN")

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
    result["embedded_value_rate"]       = _embedded_value_rate(samples, sem_type)

    # --- Tier 3 ---
    # Typo and fragmentation detection only make sense for string-typed columns.
    # Guard 1: semantic type must be string-like.
    # Guard 2: values must not all be numeric (catches UNKNOWN columns pre-enrichment).
    def _all_numeric(vals: list) -> bool:
        return bool(vals) and all(isinstance(v, (int, float)) for v, _ in vals)

    string_col = sem_type in _STRING_SEMANTIC_TYPES and not _all_numeric(most_common)

    if most_common:
        result["rare_value_rate"]                    = _rare_value_rate(most_common)
        result["suspected_typo_rate"]                = _suspected_typo_rate(most_common) if string_col else None
        result["representation_fragmentation_rate"]  = _representation_fragmentation_rate(most_common) if string_col else None
    else:
        result["rare_value_rate"]                   = None
        result["suspected_typo_rate"]               = None
        result["representation_fragmentation_rate"] = None

    result["outlier_rate"] = _outlier_rate(mean, variance, most_common)

    # --- Tier 4 ---
    result["repairability"] = _compute_repairability(result)

    return result


# ---------------------------------------------------------------------------
# Public API — entity-level
# ---------------------------------------------------------------------------

_NOISE_KEYS = (
    "missing_value_rate",
    "disguised_missing_rate",
    "format_violation_rate",
    "suspected_typo_rate",
    "representation_fragmentation_rate",
)


def compute_entity_dq_summary(
    attribute_dq: dict[str, dict],
    row_samples: list[dict] | None = None,
    attribute_semantics: dict[str, dict] | None = None,
    attribute_stats: dict[str, dict] | None = None,
) -> dict:
    """Aggregate per-attribute DQ dicts into an entity-level summary.

    Args:
        attribute_dq:         ``{attr_name: data_quality_dict}`` for every attribute.
        row_samples:          Entity row samples (from entity ``stats``).
        attribute_semantics:  ``{attr_name: value_semantics_dict}`` — enables
                              ``misplaced_value_rate`` computation.
        attribute_stats:      ``{attr_name: stats_dict}`` — provides sample_values
                              for the misplaced check.

    Returns:
        Flat dict suitable for storage as the ``"data_quality_summary"`` property.
    """
    if not attribute_dq:
        return {}

    # effective_noise_rate — mean of all non-None noise metrics across attributes
    noise_vals = [
        v for dq in attribute_dq.values()
        for k in _NOISE_KEYS
        if (v := dq.get(k)) is not None
    ]
    effective_noise = round(sum(noise_vals) / len(noise_vals), 4) if noise_vals else 0.0

    # columns with at least one noise metric > 1%
    cols_with_errors = [
        attr for attr, dq in attribute_dq.items()
        if any((dq.get(k) or 0) > 0.01 for k in _NOISE_KEYS)
    ]

    # worst attribute — highest sum of noise metrics
    def _attr_noise(dq: dict) -> float:
        return sum((dq.get(k) or 0.0) for k in _NOISE_KEYS)

    worst = max(attribute_dq, key=lambda a: _attr_noise(attribute_dq[a])) if attribute_dq else None

    # dominant error type — which noise key has the highest total across attributes
    type_totals: dict[str, float] = {}
    for dq in attribute_dq.values():
        for k in _NOISE_KEYS:
            type_totals[k] = type_totals.get(k, 0.0) + (dq.get(k) or 0.0)
    dominant = max(type_totals, key=type_totals.get) if type_totals else None

    # duplicate_row_rate from row_samples
    dup_rate: float | None = None
    if row_samples:
        row_hashes = [hash(tuple(sorted(str(v) for v in row.values()))) for row in row_samples]
        n_dupes = len(row_hashes) - len(set(row_hashes))
        dup_rate = round(n_dupes / len(row_hashes), 4)

    # rows_with_error_rate + multi_error_row_rate
    rows_err, multi_err = compute_row_error_rates(row_samples or [], attribute_semantics)

    # misplaced_value_rate per attribute (cross-column, requires both stats and semantics)
    misplaced: dict[str, float] | None = None
    if attribute_stats and attribute_semantics:
        misplaced = compute_misplaced_rates(attribute_stats, attribute_semantics)

    return {
        "effective_noise_rate":    effective_noise,
        "columns_with_errors":     cols_with_errors,
        "columns_with_error_rate": round(len(cols_with_errors) / len(attribute_dq), 4),
        "worst_attribute":         worst,
        "dominant_error_type":     dominant,
        "duplicate_row_rate":      dup_rate,
        "rows_with_error_rate":    rows_err,
        "multi_error_row_rate":    multi_err,
        "misplaced_value_rate":    misplaced,
    }
