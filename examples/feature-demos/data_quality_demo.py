"""
Data Quality Profiling — Feature Reference.

blue-data DQ profiling measures data reliability at the attribute and entity
level from already-collected stats — no LLM required.

  Pipeline:
    1. sync_all()                    — walk the live schema into the registry
    2. collect_source_stats()        — sample each column + compute frequencies
    3. enrich_source()               — deterministic semantic type inference (no LLM)
    4. compute_source_data_quality() — compute + store DQ metrics at every level

  Per-attribute property  "data_quality":

    Tier 1  (raw counts only — always available):
      missing_value_rate, fill_rate, is_partial_attribute, cardinality_ratio

    Tier 2  (sample_values + semantic type):
      disguised_missing_rate, format_violation_rate,
      heterogeneous_format_rate, embedded_value_rate
      Note: format checks need EMAIL / DATE / UUID semantic types.
      Layer 1 infers conservatively; Layer 2 (LLM) or manual annotation
      gives sharper types.  This demo annotates two columns manually.

    Tier 3  (most_common_vals frequencies + mean/variance):
      rare_value_rate, suspected_typo_rate,
      representation_fragmentation_rate, outlier_rate

    Tier 4  (derived — no extra data required):
      repairability.{deterministic, ambiguous, unrecoverable}
      misplaced_value_rate  (written back after entity summary pass)

  Per-entity property  "data_quality_summary":
    effective_noise_rate, worst_attribute, dominant_error_type,
    columns_with_error_rate, duplicate_row_rate,
    rows_with_error_rate, multi_error_row_rate, misplaced_value_rate

Run:
    pip install -e lib/
    python3 examples/feature-demos/data_quality_demo.py
"""

import tempfile

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER = "-" * 60
SOURCE  = "crm"
DB      = "crm"
COLL    = "public"
ENTITY  = "contacts"


# ---------------------------------------------------------------------------
# Helper: build a synthetic contacts table with deliberate quality issues
# ---------------------------------------------------------------------------

def _setup_registry(tmp_dir: str) -> DataRegistry:
    source = SQLiteDBSource(
        name=SOURCE,
        properties={"connection": {"database_directory": tmp_dir}},
    )
    registry = DataRegistry(store=MemoryJSONSource())
    registry.register_source(source)
    registry.create_source_database(SOURCE, DB, overwrite=True)
    registry.create_source_database_collection_entity(
        SOURCE, DB, COLL, ENTITY,
        creation_properties={
            "cols_definition": [
                {"name": "id",          "type": "INTEGER"},
                {"name": "email",       "type": "TEXT"},
                {"name": "signup_date", "type": "TEXT"},
                {"name": "country",     "type": "TEXT"},
                {"name": "salary",      "type": "REAL"},
                {"name": "status",      "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )

    rows = [
        # id  email                   signup_date    country           salary      status
        (1,  "alice@example.com",     "2024-01-15",  "US",             65000.0,   "active"),
        (2,  "bob@corp.io",           "01/16/2024",  "United States",  72000.0,   "active"),
        (3,  "N/A",                   "2024-02-01",  "UK",             58000.0,   "inactive"),
        (4,  "carol.test.org",        "02/14/2024",  "United Kingdom", 81000.0,   "active"),
        (5,  "dave@example.com",      "2024-02-20",  "US",             9999999.0, "active"),
        (6,  "eve@corp.io",           "03/05/2024",  "United States",  67000.0,   "UNKNOWN"),
        (7,  "N/A",                   "2024-03-12",  "UK",             74000.0,   "active"),
        (8,  "grace@test.org",        "03/20/2024",  "United Kingdom", 69000.0,   "inactive"),
        (9,  "henry@example.com",     "2024-04-01",  "US",             78000.0,   "active"),
        (10, "ida@corp.io",           "2024-04-10",  "United States",  62000.0,   "active"),
        (11, None,                    "2024-04-15",  "UK",             85000.0,   "pending"),
        (12, "jane@test.org",         "2024-04-22",  "United Kingdom", 71000.0,   "pnding"),
        (13, "karl@example.com",      "2024-05-01",  "US",             66000.0,   "active"),
        (14, "laura@corp.io",         "05/10/2024",  "United States",  79000.0,   "pending"),
        (15, "mike@test.org",         "2024-05-15",  "UK",             83000.0,   "active"),
        (16, "nina@example.com",      "2024-05-20",  "United Kingdom", 70000.0,   "active"),
        (17, "oscar@corp.io",         "06/01/2024",  "US",             76000.0,   "active"),
        (18, "NONE",                  "2024-06-10",  "United States",  64000.0,   "active"),
        (19, "paula@test.org",        "2024-06-20",  "UK",             88000.0,   "active"),
        (20, "quinn@example.com",     "2024-07-01",  "United Kingdom", 73000.0,   "active"),
    ]
    for r in rows:
        email_sql = f"'{r[1]}'" if r[1] is not None else "NULL"
        registry.execute_query(
            source=SOURCE, database=DB,
            query=(
                f"INSERT INTO {ENTITY} VALUES "
                f"({r[0]}, {email_sql}, '{r[2]}', '{r[3]}', {r[4]}, '{r[5]}');"
            ),
            optional_properties={"commit": True},
        )
    return registry


# ---------------------------------------------------------------------------
# 0. Dataset description
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("0. Dataset — 20 contacts rows with deliberate quality issues")
print(DIVIDER)
print("""
  Column        Injected errors
  -----------   ---------------------------------------------------------
  email         1 NULL, 2×"N/A" sentinel, 1×"NONE" sentinel,
                1 format violation (carol.test.org — missing @)
  signup_date   Mixed formats: 14 ISO (2024-01-15), 6 US (01/16/2024)
  country       Fragmented: "US"/"United States", "UK"/"United Kingdom"
  salary        One extreme outlier: 9999999 among a 58K–88K range
  status        1×"UNKNOWN" sentinel, 1×"pnding" (typo of "pending")
  id            Clean — no errors
""")


# ---------------------------------------------------------------------------
# 1. Pipeline
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("1. Pipeline: sync → collect_stats → enrich → compute_dq")
print(DIVIDER)
print()

tmp = tempfile.mkdtemp(prefix="dq-demo-")
registry = _setup_registry(tmp)

registry.sync_all(recursive=True)
attrs = registry.list_entity_attributes(SOURCE, DB, COLL, ENTITY)
print(f"  sync_all            done  ({len(attrs)} attributes registered)")

registry.collect_source_stats(SOURCE, recursive=True, sample_limit=20)
print(f"  collect_source_stats done  (sample_limit=20; top-20 frequencies; mean+variance)")

registry.enrich_source(SOURCE)
print(f"  enrich_source       done  (SemanticTypeInferencer — no LLM)")

# Tier 2 format checks need EMAIL / DATE semantic types.  The deterministic
# inferencer infers STRING for columns that have mixed or partially-invalid
# values.  LLM enrichment (Layer 2) handles this automatically in production.
# Here we annotate manually so the feature demo can show all Tier 2 metrics.
for attr, sem_type in [("email", "EMAIL"), ("signup_date", "DATE")]:
    existing = registry.get_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "value_semantics"
    ) or {}
    registry.set_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "value_semantics",
        {**existing, "semantic_type": sem_type},
    )
print(f"  annotate            done  (email→EMAIL, signup_date→DATE for Tier 2)")
print(f"                            (in production: Layer 2 / LLM handles this)")

registry.compute_source_data_quality(SOURCE)
print(f"  compute_dq          done  (data_quality + data_quality_summary written)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dq(attr: str) -> dict:
    return registry.get_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "data_quality"
    ) or {}


def _sem(attr: str) -> str:
    return (registry.get_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "value_semantics"
    ) or {}).get("semantic_type", "—")


def _f(val, w: int = 9) -> str:
    if val is None:
        return "—".ljust(w)
    if isinstance(val, bool):
        return str(val).ljust(w)
    return f"{val:.4f}".ljust(w)


ATTRS = ["id", "email", "signup_date", "country", "salary", "status"]


# ---------------------------------------------------------------------------
# 2. Tier 1 — raw counts
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("2. Tier 1 — raw counts (always available)")
print(DIVIDER)
print("""
  Computed from count + null_count + distinct_count only.
  No sample values or frequency data required.
""")
print(f"  {'attribute':<14} {'sem_type':<16} {'missing':>9}  {'fill':>9}  {'partial':<9} {'cardinality'}")
print(f"  {'-'*14} {'-'*16} {'-'*9}  {'-'*9}  {'-'*9} {'-'*11}")
for a in ATTRS:
    d = _dq(a)
    print(
        f"  {a:<14} {_sem(a):<16} "
        f"{_f(d.get('missing_value_rate'))}"
        f" {_f(d.get('fill_rate'))}"
        f" {_f(d.get('is_partial_attribute'))}"
        f"{_f(d.get('cardinality_ratio'))}"
    )


# ---------------------------------------------------------------------------
# 3. Tier 2 — format and sentinel checks
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3. Tier 2 — format and sentinel checks")
print(DIVIDER)
print("""
  Scans sample_values per attribute.

  disguised_missing   fraction matching sentinel vocabulary
                      ("N/A", "NONE", "null", "unknown", "pending", …)
  format_violation    fraction of non-null values failing the format
                      pattern implied by the column's semantic type
                      (EMAIL → ^[^@]+@[^@]+\.[^@]+$,  DATE → YYYY-MM-DD,  …)
  heterogeneous_fmt   fraction NOT in the majority date-format style
                      (ISO vs MM/DD/YYYY vs DD-MM-YYYY vs DD.MM.YYYY)
  embedded_value      fraction of long values with embedded multi-part
                      structure; skipped for FREE_TEXT / UNKNOWN columns
""")
print(f"  {'attribute':<14} {'disguised':>9}  {'fmt_viol':>9}  {'hetero_fmt':>10}  {'embedded'}")
print(f"  {'-'*14} {'-'*9}  {'-'*9}  {'-'*10}  {'-'*8}")
for a in ATTRS:
    d = _dq(a)
    print(
        f"  {a:<14} "
        f"{_f(d.get('disguised_missing_rate'))}"
        f" {_f(d.get('format_violation_rate'))}"
        f" {_f(d.get('heterogeneous_format_rate'), 10)}"
        f" {_f(d.get('embedded_value_rate'))}"
    )


# ---------------------------------------------------------------------------
# 4. Tier 3 — frequency-based metrics
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("4. Tier 3 — frequency-based (top-20 most_common_vals + mean/variance)")
print(DIVIDER)
print("""
  rare_value          fraction of distinct values appearing exactly once
  suspected_typo      fraction of singleton values within edit-distance 2
                      of a frequent value  (None for numeric columns)
  fragmentation       fraction of distinct values that are abbreviations of
                      another value in the column
                      ("UK" initials-match "United Kingdom";
                       "US" prefix-matches "United States")
  outlier_rate        fraction of rows (weighted by frequency) > 3σ from
                      the column mean  (None for non-numeric columns)
""")
print(f"  {'attribute':<14} {'rare':>9}  {'typo':>9}  {'frag':>9}  {'outlier'}")
print(f"  {'-'*14} {'-'*9}  {'-'*9}  {'-'*9}  {'-'*7}")
for a in ATTRS:
    d = _dq(a)
    print(
        f"  {a:<14} "
        f"{_f(d.get('rare_value_rate'))}"
        f" {_f(d.get('suspected_typo_rate'))}"
        f" {_f(d.get('representation_fragmentation_rate'))}"
        f" {_f(d.get('outlier_rate'))}"
    )


# ---------------------------------------------------------------------------
# 5. Tier 4 — repairability (derived)
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("5. Tier 4 — repairability (derived from Tier 1–3 metrics)")
print(DIVIDER)
print("""
  Derived without any additional data collection.

  deterministic   errors fixable by rule (format normalization, universal
                  sentinel replacement, single nearest-neighbour typo fix)
                  ≈ format_violation + 0.6 × disguised_missing
  ambiguous       errors requiring inference (domain-specific sentinels,
                  typos with multiple plausible candidates, frag variants)
                  ≈ suspected_typo + fragmentation + 0.4 × disguised_missing
  unrecoverable   true nulls where the original value is gone
                  ≈ missing_value_rate
""")
print(f"  {'attribute':<14} {'deterministic':>13}  {'ambiguous':>9}  {'unrecoverable'}")
print(f"  {'-'*14} {'-'*13}  {'-'*9}  {'-'*13}")
for a in ATTRS:
    r = _dq(a).get("repairability") or {}
    print(
        f"  {a:<14} "
        f"{_f(r.get('deterministic'), 13)}"
        f" {_f(r.get('ambiguous'))}"
        f" {_f(r.get('unrecoverable'))}"
    )


# ---------------------------------------------------------------------------
# 6. Entity summary
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("6. Entity summary — data_quality_summary")
print(DIVIDER)
print()

summary = registry.get_source_database_collection_entity_property(
    SOURCE, DB, COLL, ENTITY, "data_quality_summary"
) or {}

print(f"  effective_noise_rate     {summary.get('effective_noise_rate', '—')}")
print(f"  columns_with_error_rate  {summary.get('columns_with_error_rate', '—')}")
print(f"  worst_attribute          {summary.get('worst_attribute', '—')}")
print(f"  dominant_error_type      {summary.get('dominant_error_type', '—')}")
print(f"  duplicate_row_rate       {summary.get('duplicate_row_rate', '—')}")
print(f"  rows_with_error_rate     {summary.get('rows_with_error_rate', '—')}")
print(f"  multi_error_row_rate     {summary.get('multi_error_row_rate', '—')}")

cols_err = summary.get("columns_with_errors", [])
print(f"  columns_with_errors ({len(cols_err)}):  {cols_err}")

misplaced = summary.get("misplaced_value_rate") or {}
print()
print("  misplaced_value_rate per attribute:")
for a, rate in misplaced.items():
    print(f"    {a:<14} {rate:.4f}")


# ---------------------------------------------------------------------------
# 7. Metric reference
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("7. Metric reference")
print(DIVIDER)
print("""
  Metric name                         Stored on    Tier  Needs
  ----------------------------------  -----------  ----  ----------------------
  missing_value_rate                  attribute    1     count + null_count
  fill_rate                           attribute    1     count + null_count
  is_partial_attribute                attribute    1     count + null_count
  cardinality_ratio                   attribute    1     count + distinct_count
  disguised_missing_rate              attribute    2     sample_values
  format_violation_rate               attribute    2     sample_values + sem_type
  heterogeneous_format_rate           attribute    2     sample_values + DATE type
  embedded_value_rate                 attribute    2     sample_values + sem_type
  rare_value_rate                     attribute    3     most_common_vals
  suspected_typo_rate                 attribute    3     most_common_vals
  representation_fragmentation_rate   attribute    3     most_common_vals
  outlier_rate                        attribute    3     most_common_vals + mean/var
  repairability.{det,amb,unrec}       attribute    4     Tier 1–3 metrics
  misplaced_value_rate                attribute    4†    cross-column sample_values
  effective_noise_rate                entity       —     all attribute DQ dicts
  columns_with_errors                 entity       —     all attribute DQ dicts
  columns_with_error_rate             entity       —     all attribute DQ dicts
  worst_attribute                     entity       —     all attribute DQ dicts
  dominant_error_type                 entity       —     all attribute DQ dicts
  duplicate_row_rate                  entity       —     row_samples
  rows_with_error_rate                entity       —     row_samples + sem_types
  multi_error_row_rate                entity       —     row_samples + sem_types
  misplaced_value_rate (map)          entity       —     sample_values + sem_types

  † written back to each attribute after the entity summary pass
""")

print("Demo complete.")
