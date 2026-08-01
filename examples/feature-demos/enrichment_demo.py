"""
Enrichment Pipeline Reference.

blue-data enrichment adds semantic intelligence to registry records in two layers:

  Layer 1 — Deterministic (no LLM, no API key, always runs)
    Inspects column names, declared types, and sample values to infer:
    • semantic_type    — what kind of value this column holds
                         (INTEGER, DATE, CURRENCY_AMOUNT, ENUM_CATEGORY, …)
    • semantic_role    — how the column functions in the table
                         (IDENTIFIER, EVENT_TIME, EVIDENCE, SEGMENTATION_DRIVER, …)
    • quantitative_vst — how numeric columns should be aggregated
                         (COUNT, AMOUNT, RATE, DURATION)
    • process_semantics — whether the table is an event log; which column is the
                          time axis and which column uniquely identifies a row
    • semantic_links   — pairs of columns whose values co-vary across the table

  Layer 2 — LLM-augmented (requires llm_fn + API key, runs on top of Layer 1)
    Sends column metadata to an LLM and parses the response to add:
    • value_semantics   — richer semantic type with confidence and rationale
    • semantic_discovery — domain subcategory ("transaction amount", "date of hire", …)

    This demo enables only VSI + SDI (2 LLM calls per attribute) and disables
    Domain Concept Mapping and Interpretive Value Semantics to keep runtime short.
    In production you would enable all flags for a one-time enrichment pass.

The llm_fn contract
-------------------
MetaData accepts any callable with the signature:

    llm_fn(prompt: str) -> str

You can inject any LLM provider — Anthropic, OpenAI, a local model, or a test
stub.  The demo below wires the Anthropic SDK (claude-haiku-4-5-20251001).

Run:
    pip install -e lib/
    python3 examples/feature-demos/enrichment_demo.py          # Layer 1 only
    ANTHROPIC_API_KEY=sk-ant-... \\
    python3 examples/feature-demos/enrichment_demo.py          # Layer 1 + Layer 2
"""

import os
import sqlite3
import tempfile

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.registry.enrichment.semantic_types import SemanticTypeInferencer
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER = "-" * 60


# ---------------------------------------------------------------------------
# Helper: build a synthetic purchases table in SQLite
# ---------------------------------------------------------------------------

def _setup_registry(tmp_dir: str, metadata_enricher=None) -> DataRegistry:
    """Create a DataRegistry backed by SQLite with a purchases table."""
    source = SQLiteDBSource(
        name="sqlite",
        properties={"connection": {"database_directory": tmp_dir}},
    )
    registry = DataRegistry(
        store=MemoryJSONSource(),
        metadata_enricher=metadata_enricher,
    )
    registry.register_source(source)

    registry.create_source_database("sqlite", "sales", overwrite=True)
    registry.create_source_database_collection_entity(
        "sqlite", "sales", "public", "purchases",
        creation_properties={
            "cols_definition": [
                {"name": "id",            "type": "INTEGER"},
                {"name": "user_id",       "type": "INTEGER"},
                {"name": "purchase_date", "type": "TEXT"},
                {"name": "amount",        "type": "REAL"},
                {"name": "category",      "type": "TEXT"},
                {"name": "status",        "type": "TEXT"},
                {"name": "discount_pct",  "type": "REAL"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )

    rows = [
        (1,  101, "2024-01-15", 49.99,  "electronics", "completed", 0.0),
        (2,  102, "2024-01-16", 129.50, "clothing",    "completed", 10.0),
        (3,  101, "2024-02-01", 9.99,   "books",       "completed", 0.0),
        (4,  103, "2024-02-14", 299.00, "electronics", "returned",  5.0),
        (5,  104, "2024-02-20", 24.99,  "books",       "completed", 0.0),
        (6,  102, "2024-03-05", 74.50,  "clothing",    "completed", 15.0),
        (7,  105, "2024-03-12", 199.99, "electronics", "completed", 0.0),
        (8,  101, "2024-03-20", 14.99,  "books",       "pending",   0.0),
        (9,  103, "2024-04-01", 59.99,  "clothing",    "completed", 20.0),
        (10, 106, "2024-04-10", 349.00, "electronics", "completed", 0.0),
        (11, 104, "2024-04-15", 12.99,  "books",       "completed", 0.0),
        (12, 107, "2024-04-22", 89.99,  "clothing",    "completed", 10.0),
        (13, 105, "2024-05-01", 399.99, "electronics", "pending",   0.0),
        (14, 108, "2024-05-10", 29.99,  "books",       "completed", 0.0),
        (15, 101, "2024-05-15", 54.00,  "clothing",    "completed", 5.0),
        (16, 106, "2024-06-01", 19.99,  "books",       "completed", 0.0),
        (17, 102, "2024-06-10", 149.99, "electronics", "returned",  0.0),
        (18, 109, "2024-06-20", 39.99,  "clothing",    "completed", 25.0),
        (19, 107, "2024-07-01", 79.99,  "electronics", "completed", 0.0),
        (20, 110, "2024-07-15", 7.99,   "books",       "completed", 0.0),
    ]
    for row in rows:
        registry.execute_query(
            source="sqlite",
            database="sales",
            query=(
                f"INSERT INTO purchases VALUES "
                f"({row[0]}, {row[1]}, '{row[2]}', {row[3]}, "
                f"'{row[4]}', '{row[5]}', {row[6]});"
            ),
            optional_properties={"commit": True},
        )
    return registry


# ---------------------------------------------------------------------------
# 0. SemanticTypeInferencer — standalone usage
# ---------------------------------------------------------------------------
# Before wiring it into the full pipeline, you can use SemanticTypeInferencer
# directly to classify a list of sample values.  This is the same logic Layer 1
# runs internally on each column's stored sample values.

print()
print(DIVIDER)
print("0. SemanticTypeInferencer — standalone usage")
print(DIVIDER)
print("""
  SemanticTypeInferencer inspects a list of sample values and returns a
  semantic_type + confidence.  It runs without any LLM or API key.
  The full pipeline calls this internally for every registered attribute.
""")

inferencer = SemanticTypeInferencer()

samples = {
    "integers":    [1, 2, 3, 4, 5],
    "floats":      [9.99, 14.99, 24.50, 199.0],
    "dates":       ["2024-01-15", "2024-02-01", "2024-03-12"],
    "categories":  ["electronics", "clothing", "books", "electronics", "clothing"],
    "free text":   ["this is a free form description that is quite long and unique across rows " + str(i) for i in range(20)],
    "emails":      ["alice@example.com", "bob@corp.io", "carol@test.org"],
    "percentages": [0.0, 5.0, 10.0, 15.0, 20.0, 25.0],
}

for label, values in samples.items():
    result = inferencer.infer(values)
    print(f"  {label:<12} → {result['semantic_type']:<20} (confidence={result['confidence']:.2f})")


# ---------------------------------------------------------------------------
# Layer 1 — Deterministic enrichment (no LLM required)
# ---------------------------------------------------------------------------
# Steps:
#   1. sync_all()              — walks the live SQLite schema into the registry
#   2. collect_source_stats()  — samples each column so the inferencer has values
#   3. enrich_source_metadata()— runs Layer 1 (and Layer 2 if llm_fn is set)
#
# Layer 1 writes several properties to each attribute record:
#   • value_semantics  — semantic type detected from samples
#   • semantic_role    — functional role in the table (IDENTIFIER, EVIDENCE, …)
#   • quantitative_vst — aggregation role for numeric columns
#
# And entity-level properties:
#   • process_semantics — event-log detection (row_semantics, event_time)
#   • semantic_links    — column pairs that co-vary

print()
print(DIVIDER)
print("Layer 1 — Deterministic enrichment  (llm_fn=None)")
print(DIVIDER)
print("""
  Pipeline: sync → collect_stats → enrich_source_metadata(llm_fn=None)
  No API key needed. Reads column names, declared types, and sample values.
""")

tmp_a = tempfile.mkdtemp(prefix="enrich-demo-a-")
enricher_a = MetaData(llm_fn=None)
registry_a = _setup_registry(tmp_a, metadata_enricher=enricher_a)

registry_a.sync_all(recursive=True)
registry_a.collect_source_stats("sqlite", recursive=True)
registry_a.enrich_source_metadata("sqlite", recursive=True, rebuild=False)

print("  Column-level enrichment results:")
print(f"  {'attribute':<15} {'semantic_type':<22} {'semantic_role':<20} {'quantitative_vst'}")
print(f"  {'-'*15} {'-'*22} {'-'*20} {'-'*16}")

for attr_name in ("id", "user_id", "purchase_date", "amount", "category", "status", "discount_pct"):
    vsi  = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "value_semantics") or {}
    role = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "semantic_role") or {}
    qvst = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "quantitative_vst") or {}
    print(
        f"  {attr_name:<15} {vsi.get('semantic_type','—'):<22} "
        f"{role.get('primary_role','—'):<20} {qvst.get('role','—')}"
    )

print()
print("  Entity-level enrichment results:")

ps = registry_a.get_source_database_collection_entity_property(
    "sqlite", "sales", "public", "purchases", "process_semantics"
)
if ps:
    print(f"  process_semantics:")
    print(f"    row_semantics = {ps.get('row_semantics')}  "
          f"(this table is treated as an event log)")
    print(f"    event_time    = {ps.get('event_time')}  "
          f"(the column that anchors each event in time)")

links = registry_a.get_source_database_collection_entity_property(
    "sqlite", "sales", "public", "purchases", "semantic_links"
)
if links:
    print(f"  semantic_links  ({len(links)} pair(s) detected):")
    for lnk in links[:3]:
        print(f"    {lnk['source']} → {lnk['target']}  "
              f"({lnk.get('relationship','—')}, confidence={lnk.get('confidence',0):.2f})")

print()
print("  Layer 1 complete — no LLM was called.")


# ---------------------------------------------------------------------------
# Layer 2 — LLM-augmented enrichment
# ---------------------------------------------------------------------------
# Layer 2 runs on top of Layer 1.  It sends each column's name, type, and
# sample values to an LLM and asks two questions:
#
#   VSI — Value Semantics Inference
#         "What is the real-world meaning of these values?"
#         Produces a richer semantic_type with confidence and a rationale string.
#
#   SDI — Semantic Discovery Inference
#         "What domain concept does this column represent?"
#         Produces a subcategory label ("transaction amount", "date of hire", …)
#
# Domain Concept Mapping (DCM) and Interpretive Value Semantics (IVS) are
# disabled here to keep the demo fast.  Enable them in production by removing
# the properties overrides below.  Each costs one additional LLM call per column.
#
# Idempotency: rebuild=False (default) skips columns that already have a stored
# value for that property.  Re-run with rebuild=True to overwrite everything.

api_key = os.environ.get("ANTHROPIC_API_KEY")

if not api_key:
    print()
    print(DIVIDER)
    print("Layer 2 — LLM-augmented enrichment  (SKIPPED — no ANTHROPIC_API_KEY)")
    print(DIVIDER)
    print("""
  Set ANTHROPIC_API_KEY to run the LLM enrichment layer.
  Install the SDK first if needed:
    pip install anthropic
    pip install "blue-data[llm]"

  With an API key, Layer 2 adds:
    • value_semantics    — richer type with confidence and rationale (VSI)
    • semantic_discovery — domain subcategory label per column (SDI)
""")
else:
    print()
    print(DIVIDER)
    print("Layer 2 — LLM-augmented enrichment  (claude-haiku-4-5-20251001)")
    print(DIVIDER)
    print("""
  Layer 2 runs on top of Layer 1 results.  For each column it calls the LLM
  twice: once for VSI (richer semantic type) and once for SDI (domain label).
  DCM and IVS are disabled in this demo to keep runtime short.
""")

    import anthropic

    _client = anthropic.Anthropic(api_key=api_key)

    def llm_fn(prompt: str) -> str:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    call_count = [0]
    def instrumented_llm_fn(prompt: str) -> str:
        call_count[0] += 1
        return llm_fn(prompt)

    # Disable DCM and IVS — 2 LLM calls per column instead of 4.
    # Remove these overrides to run the full enrichment suite.
    fast_properties = {
        "enable_domain_concept_mapping":  False,
        "enable_interpretive_semantics":  False,
    }

    tmp_b = tempfile.mkdtemp(prefix="enrich-demo-b-")
    enricher_b = MetaData(llm_fn=instrumented_llm_fn, properties=fast_properties)
    registry_b = _setup_registry(tmp_b, metadata_enricher=enricher_b)

    registry_b.sync_all(recursive=True)
    registry_b.collect_source_stats("sqlite", recursive=True)

    print("  Running enrich_source_metadata (rebuild=False) …")
    registry_b.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
    print(f"  LLM called {call_count[0]} time(s).")

    print()
    print("  LLM-enriched column results:")
    print(f"  {'attribute':<15} {'VSI semantic_type':<25} {'SDI subcategory'}")
    print(f"  {'-'*15} {'-'*25} {'-'*30}")

    for attr_name in ("id", "user_id", "purchase_date", "amount", "category", "status", "discount_pct"):
        vsi = registry_b.get_source_database_collection_entity_attribute_property(
            "sqlite", "sales", "public", "purchases", attr_name, "value_semantics"
        ) or {}
        sdi = registry_b.get_source_database_collection_entity_attribute_property(
            "sqlite", "sales", "public", "purchases", attr_name, "semantic_discovery"
        ) or {}
        print(
            f"  {attr_name:<15} {vsi.get('semantic_type','—'):<25} "
            f"{sdi.get('subcategory','—')}"
        )

    entity_desc = registry_b.get_source_database_collection_entity_description(
        "sqlite", "sales", "public", "purchases"
    )
    if entity_desc:
        print(f"\n  Auto-generated entity description:")
        print(f"    {entity_desc}")

    print()
    print("  Idempotency check:")
    print("  Running a second pass with rebuild=False — already-enriched columns are skipped.")
    before = call_count[0]
    registry_b.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
    print(f"  LLM called {call_count[0] - before} additional time(s) (expected 0).")
    print()
    print("  To force re-enrichment, pass rebuild=True — every property is overwritten.")
    print("  Layer 2 complete.")


# ---------------------------------------------------------------------------
# Property reference
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Enrichment property reference")
print(DIVIDER)
print("""
  Every property below is stored on the attribute or entity record in the
  registry and is available to search, NL2SQL, and downstream agents.
""")

properties = {
    "value_semantics":               "Semantic type of column values (INTEGER, DATE, ENUM_CATEGORY, …)  [L1+L2]",
    "semantic_role":                 "Structural role: IDENTIFIER, EVENT_TIME, EVIDENCE, SEGMENTATION_DRIVER  [L1]",
    "quantitative_vst":              "Aggregation role for numeric columns: COUNT, AMOUNT, RATE, DURATION  [L1]",
    "process_semantics":             "Event-log detection: row_semantics, event_time, event_key  [L1]",
    "semantic_links":                "Column pairs whose values co-vary across the table  [L1]",
    "semantic_discovery":            "LLM domain subcategory label and confidence  [L2]",
    "domain_concept":                "Canonical domain concept this column maps to  [L2]",
    "interpretive_semantics":        "Human-readable interpretation of coded/ordinal values  [L2]",
    "value_axis":                    "Whether the column can serve as a quantitative axis  [L1]",
    "safe_aggregation":              "Which aggregations are safe to apply (SUM, AVG, …)  [L1]",
    "process_patterns":              "Recurring temporal patterns detected in the event data  [L1]",
    "process_trends":                "Trend signals over time  [L1]",
    "conditional_value_distribution": "Value distribution conditioned on another column  [L1]",
}
for prop, description in properties.items():
    print(f"  {prop:<35} {description}")

print()
print("Demo complete.")
