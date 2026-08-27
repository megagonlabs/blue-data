"""
Data Quality Profiling — Before and After.

Story: A vendor delivers a CRM export.  The schema looks correct — six columns,
no type errors, every row present.  An AI agent is about to query it.

Without DQ profiling the agent runs directly on the raw data and returns a
badly skewed answer.  With DQ profiling blue-data surfaces four concrete issues
before any query runs, and the corrected query returns the right result.

  Quantitative result
    naive query   → 5 contacts,  avg salary $2,056,999  (wrong)
    DQ-informed   → 7 contacts,  avg salary $69,000     (correct)

Run:
    pip install -e lib/
    python3 examples/scenario-demos/data_quality_demo.py
"""

import tempfile

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER = "=" * 64
SOURCE  = "crm"
DB      = "crm"
COLL    = "public"
ENTITY  = "contacts"


# ---------------------------------------------------------------------------
# Dataset: a "clean-looking" CRM export with hidden quality issues
# ---------------------------------------------------------------------------

ROWS = [
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


def _build_registry(tmp_dir: str) -> DataRegistry:
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
    for r in ROWS:
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
# Setup
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Data Quality Profiling — Before and After")
print(DIVIDER)
print("""
  Dataset : 20-row CRM contact export
  Schema  : id, email, signup_date, country, salary, status
  Goal    : average salary of active contacts in the US

  The dataset looks structurally correct — no missing columns, no obvious
  type errors.  But hidden quality issues cause a naive query to return
  a value 29× higher than the true figure.
""")

tmp = tempfile.mkdtemp(prefix="dq-scenario-")
registry = _build_registry(tmp)
registry.sync_all(recursive=True)
registry.collect_source_stats(SOURCE, recursive=True, sample_limit=20)

# Layer 1 enrichment (deterministic, no LLM).
# Annotate email + signup_date explicitly so format checks are precise.
# In production: Layer 2 / LLM enrichment handles this automatically.
registry.enrich_source(SOURCE)
for attr, sem_type in [("email", "EMAIL"), ("signup_date", "DATE")]:
    existing = registry.get_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "value_semantics"
    ) or {}
    registry.set_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "value_semantics",
        {**existing, "semantic_type": sem_type},
    )


# ---------------------------------------------------------------------------
# Step 1 — Naive query (before DQ)
# ---------------------------------------------------------------------------

print(DIVIDER)
print("Step 1 — Naive query: 'What is the avg salary of active US contacts?'")
print(DIVIDER)

SQL_NAIVE = (
    "SELECT COUNT(*), AVG(salary) FROM contacts "
    "WHERE status = 'active' AND country = 'US'"
)
print(f"\n  SQL:  {SQL_NAIVE}\n")

rows = registry.execute_query(
    source=SOURCE,
    query=SQL_NAIVE,
    database=DB,
    collection=COLL,
)
count_naive = rows[0]["COUNT(*)"]
avg_naive   = rows[0]["AVG(salary)"]
print(f"  Result:  {count_naive} contacts,  avg salary ${avg_naive:,.2f}")
print("""
  Something is wrong.  $2M+ is not a realistic average salary.
  And only 5 contacts — the dataset has 14 rows with status='active'.
  The query is syntactically correct but the data isn't ready.
""")


# ---------------------------------------------------------------------------
# Step 2 — Run DQ profiling
# ---------------------------------------------------------------------------

print(DIVIDER)
print("Step 2 — DQ profiling: sync → collect_stats → enrich → compute_dq")
print(DIVIDER)
print()

registry.compute_source_data_quality(SOURCE)
print("  compute_source_data_quality complete.\n")


def _dq(attr: str) -> dict:
    return registry.get_source_database_collection_entity_attribute_property(
        SOURCE, DB, COLL, ENTITY, attr, "data_quality"
    ) or {}


# ---------------------------------------------------------------------------
# Step 3 — What DQ found
# ---------------------------------------------------------------------------

print(DIVIDER)
print("Step 3 — DQ findings (4 issues across 3 columns)")
print(DIVIDER)

summary = registry.get_source_database_collection_entity_property(
    SOURCE, DB, COLL, ENTITY, "data_quality_summary"
) or {}

n_cols = len(registry.list_entity_attributes(SOURCE, DB, COLL, ENTITY))
n_err  = len(summary.get("columns_with_errors", []))

print(f"""
  Entity-level
    {n_err} of {n_cols} columns flagged
    {summary.get('rows_with_error_rate', 0):.0%} of rows have at least one error
    {summary.get('multi_error_row_rate', 0):.0%} of rows have two or more errors
    worst column : {summary.get('worst_attribute', '—')}
""")

# --- Issue 1: salary outlier ---
d_sal = _dq("salary")
outlier = d_sal.get("outlier_rate") or 0.0
rep = d_sal.get("repairability") or {}
print(f"  Issue 1 — salary: outlier detected")
print(f"    outlier_rate       {outlier:.2%}  (rows > 3σ from mean)")
print(f"    repairability      deterministic={rep.get('deterministic', 0):.2f}  "
      f"ambiguous={rep.get('ambiguous', 0):.2f}  "
      f"unrecoverable={rep.get('unrecoverable', 0):.2f}")
print(f"    value 9999999 is likely a test or placeholder record")
print()

# --- Issue 2: country fragmentation ---
d_cou = _dq("country")
frag = d_cou.get("representation_fragmentation_rate") or 0.0
rep = d_cou.get("repairability") or {}
print(f"  Issue 2 — country: representation fragmentation")
print(f"    fragmentation_rate {frag:.2%}  (abbreviation ↔ full-form variants)")
print(f"    repairability      deterministic={rep.get('deterministic', 0):.2f}  "
      f"ambiguous={rep.get('ambiguous', 0):.2f}  "
      f"unrecoverable={rep.get('unrecoverable', 0):.2f}")
print(f"    'US' and 'United States' are the same entity — query misses half")
print()

# --- Issue 3: email quality ---
d_em = _dq("email")
miss = d_em.get("missing_value_rate") or 0.0
disg = d_em.get("disguised_missing_rate") or 0.0
fmtv = d_em.get("format_violation_rate") or 0.0
rep  = d_em.get("repairability") or {}
print(f"  Issue 3 — email: missing and invalid values")
print(f"    missing_value_rate    {miss:.2%}  (true nulls)")
print(f"    disguised_missing     {disg:.2%}  (\"N/A\" × 2, \"NONE\" × 1)")
print(f"    format_violation      {fmtv:.2%}  (carol.test.org — no @ sign)")
print(f"    repairability         deterministic={rep.get('deterministic', 0):.2f}  "
      f"ambiguous={rep.get('ambiguous', 0):.2f}  "
      f"unrecoverable={rep.get('unrecoverable', 0):.2f}")
print()

# --- Issue 4: status typo ---
d_st = _dq("status")
typo = d_st.get("suspected_typo_rate") or 0.0
disg = d_st.get("disguised_missing_rate") or 0.0
rep  = d_st.get("repairability") or {}
print(f"  Issue 4 — status: sentinel and typo")
print(f"    disguised_missing     {disg:.2%}  (\"UNKNOWN\" sentinel)")
print(f"    suspected_typo_rate   {typo:.2%}  (\"pnding\" — edit-distance 1 from \"pending\")")
print(f"    repairability         deterministic={rep.get('deterministic', 0):.2f}  "
      f"ambiguous={rep.get('ambiguous', 0):.2f}  "
      f"unrecoverable={rep.get('unrecoverable', 0):.2f}")
print()


# ---------------------------------------------------------------------------
# Step 4 — DQ-informed query
# ---------------------------------------------------------------------------

print(DIVIDER)
print("Step 4 — DQ-informed query: normalize country + filter outlier")
print(DIVIDER)

SQL_CLEAN = (
    "SELECT COUNT(*), AVG(salary) FROM contacts "
    "WHERE status = 'active' "
    "  AND country IN ('US', 'United States') "
    "  AND salary < 150000"
)
print(f"\n  Fixes applied:")
print(f"    country: expand to both 'US' and 'United States'  (fragmentation fix)")
print(f"    salary:  exclude rows above $150K                 (outlier filter)")
print(f"\n  SQL:  {SQL_CLEAN}\n")

rows = registry.execute_query(
    source=SOURCE,
    query=SQL_CLEAN,
    database=DB,
    collection=COLL,
)
count_clean = rows[0]["COUNT(*)"]
avg_clean   = rows[0]["AVG(salary)"]
print(f"  Result:  {count_clean} contacts,  avg salary ${avg_clean:,.2f}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Summary")
print(DIVIDER)
print(f"""
                   Before DQ          After DQ
  ─────────────    ──────────────     ──────────────
  Contacts found   {count_naive}                  {count_clean}
  Avg salary       ${avg_naive:>13,.2f}     ${avg_clean:>13,.2f}
  Error factor     {avg_naive / avg_clean:.1f}×  too high      —

  DQ profiling identified:
    • salary    outlier_rate = {(d_sal.get('outlier_rate') or 0):.2%}  → filter before aggregation
    • country   fragmentation = {(d_cou.get('representation_fragmentation_rate') or 0):.0%}  → normalize variants
    • email     {(d_em.get('missing_value_rate') or 0):.0%} missing + {(d_em.get('disguised_missing_rate') or 0):.0%} disguised  → do not use as join key
    • status    typo_rate = {(d_st.get('suspected_typo_rate') or 0):.0%}  → normalize before filtering

  All metrics are stored as registry properties and available to agents
  before any query runs.  No LLM call required.
""")

print("Demo complete.")
