"""
Enrichment pipeline end-to-end demo.

The enrichment layer adds two kinds of intelligence to registry records:

  Layer 1 — Deterministic (always runs, no LLM, no API key needed)
    • SemanticTypeInferencer: classifies every attribute's values into a
      semantic type (INTEGER, FLOAT, DATE, EMAIL, ENUM_CATEGORY, etc.)
    • Deterministic MetaData signals: process semantics, semantic roles,
      value-axis eligibility, quantitative VST roles, semantic links

  Layer 2 — LLM-augmented (runs when llm_fn is provided)
    • Value Semantics Inference (VSI): richer semantic type analysis
    • Semantic Discovery Inference (SDI): domain subcategory + confidence
    • Domain Concept Mapping (DCM): maps attribute to a known concept
    • Interpretive Value Semantics (IVS): human-readable value meaning
    • Entity descriptions: auto-generated table summaries

The llm_fn contract
-------------------
MetaData accepts any callable with the signature:

    llm_fn(prompt: str) -> str

The function receives a plain-text prompt and must return a plain-text
(or JSON) response string.  You can wire any LLM provider — the demo
below shows the Anthropic SDK (claude-opus-4-8), but you can swap in
OpenAI, a local model, or a test stub.

Prerequisite order (must be followed)
--------------------------------------
    sync_all(recursive=True)            # discover schema
    collect_source_stats(recursive=True) # gather sample values
    enrich_source_metadata(...)         # run enrichment

Stats are required because the inferencer reads sample_values to detect
semantic types and compute signals.

Run from lib/:
    PYTHONPATH=src/blue-data python3 ../examples/enrichment_demo.py

For LLM-augmented enrichment, set your API key first:
    export ANTHROPIC_API_KEY=sk-ant-...

Install the Anthropic SDK (optional, only for Mode B):
    pip install anthropic
    # or: pip install "blue-data[llm]"
"""
import json
import os
import tempfile

from registry.data_registry import DataRegistry
from registry.enrichment.metadata import MetaData
from registry.enrichment.semantic_types import SemanticTypeInferencer
from source.json.memory_json_source import MemoryJSONSource
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER = "-" * 60


# ---------------------------------------------------------------------------
# Helper: build a realistic purchases dataset
# ---------------------------------------------------------------------------

def _setup_registry(tmp_dir: str, metadata_enricher=None) -> DataRegistry:
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

print()
print(DIVIDER)
print("0. SemanticTypeInferencer — standalone usage")
print(DIVIDER)

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
# MODE A: Deterministic enrichment — no LLM required
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("MODE A: Deterministic enrichment  (llm_fn=None)")
print(DIVIDER)

tmp_a = tempfile.mkdtemp(prefix="enrich-demo-a-")
enricher_a = MetaData(llm_fn=None)
registry_a = _setup_registry(tmp_a, metadata_enricher=enricher_a)

# Prerequisite order: sync → stats → enrich
registry_a.sync_all(recursive=True)
registry_a.collect_source_stats("sqlite", recursive=True)
registry_a.enrich_source_metadata("sqlite", recursive=True, rebuild=False)

print("\nDeterministic enrichments written to registry:")
for attr_name in ("id", "user_id", "purchase_date", "amount", "category", "status", "discount_pct"):
    vsi = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "value_semantics"
    )
    role = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "semantic_role"
    )
    qvst = registry_a.get_source_database_collection_entity_attribute_property(
        "sqlite", "sales", "public", "purchases", attr_name, "quantitative_vst"
    )
    sem_type = vsi["semantic_type"] if vsi else "—"
    primary_role = role.get("primary_role", "—") if role else "—"
    q_role = qvst.get("role", "—") if qvst else "—"
    print(f"  {attr_name:<15} type={sem_type:<20} role={primary_role:<14} qvst={q_role}")

ps = registry_a.get_source_database_collection_entity_property(
    "sqlite", "sales", "public", "purchases", "process_semantics"
)
if ps:
    print(f"\nProcess semantics: row_semantics={ps.get('row_semantics')}, "
          f"event_time={ps.get('event_time')}")

links = registry_a.get_source_database_collection_entity_property(
    "sqlite", "sales", "public", "purchases", "semantic_links"
)
if links:
    print(f"Semantic links detected: {len(links)} pair(s)")
    for lnk in links[:3]:
        rel = lnk.get("relationship", "—")
        conf = lnk.get("confidence", 0.0)
        print(f"  {lnk['source']} → {lnk['target']}  ({rel}, confidence={conf:.2f})")

value_axes = registry_a.get_source_database_collection_entity_property(
    "sqlite", "sales", "public", "purchases", "value_axis"
)
if value_axes:
    print(f"Value-axis eligible attributes: {value_axes}")

print("\nMode A complete — no LLM was called.")


# ---------------------------------------------------------------------------
# MODE B: LLM-augmented enrichment
# ---------------------------------------------------------------------------

api_key = os.environ.get("ANTHROPIC_API_KEY")

if not api_key:
    print()
    print(DIVIDER)
    print("MODE B: LLM-augmented enrichment  (SKIPPED — no ANTHROPIC_API_KEY)")
    print(DIVIDER)
    print("  Set ANTHROPIC_API_KEY to run the full LLM pipeline.")
    print("  Install: pip install anthropic  (or pip install 'blue-data[llm]')")
else:
    print()
    print(DIVIDER)
    print("MODE B: LLM-augmented enrichment")
    print(DIVIDER)

    # -------------------------------------------------------------------
    # Wire llm_fn — any callable(str) -> str works here.
    # We use the Anthropic SDK with claude-opus-4-8.
    # You can swap this for any other provider.
    # -------------------------------------------------------------------
    import anthropic  # pip install anthropic

    _client = anthropic.Anthropic(api_key=api_key)

    def llm_fn(prompt: str) -> str:
        """Send prompt to Claude, return the text response."""
        response = _client.messages.create(
            model="claude-opus-4-8",
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

    tmp_b = tempfile.mkdtemp(prefix="enrich-demo-b-")
    enricher_b = MetaData(llm_fn=instrumented_llm_fn)
    registry_b = _setup_registry(tmp_b, metadata_enricher=enricher_b)

    registry_b.sync_all(recursive=True)
    registry_b.collect_source_stats("sqlite", recursive=True)

    print("Running enrich_source_metadata (first pass, rebuild=False) …")
    registry_b.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
    first_pass_calls = call_count[0]
    print(f"LLM called {first_pass_calls} time(s) on first pass.")

    print("\nLLM-enriched attributes:")
    for attr_name in ("user_id", "purchase_date", "amount", "category", "status", "discount_pct"):
        vsi = registry_b.get_source_database_collection_entity_attribute_property(
            "sqlite", "sales", "public", "purchases", attr_name, "value_semantics"
        )
        sdi = registry_b.get_source_database_collection_entity_attribute_property(
            "sqlite", "sales", "public", "purchases", attr_name, "semantic_discovery"
        )
        sem_type = vsi.get("semantic_type", "—") if vsi else "—"
        subcategory = sdi.get("subcategory", "—") if sdi else "—"
        print(f"  {attr_name:<15} VSI type={sem_type:<20} SDI subcategory={subcategory}")

    entity_desc = registry_b.get_source_database_collection_entity_description(
        "sqlite", "sales", "public", "purchases"
    )
    print(f"\nAuto-generated entity description:\n  {entity_desc}")

    # -------------------------------------------------------------------
    # Idempotency: second pass with rebuild=False must not call LLM again
    # -------------------------------------------------------------------
    print("\nRunning second pass (rebuild=False) — no LLM calls expected …")
    registry_b.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
    second_pass_calls = call_count[0] - first_pass_calls
    print(f"LLM called {second_pass_calls} additional time(s) on second pass (expected 0).")

    # Force re-enrichment by passing rebuild=True
    print("\nRunning third pass (rebuild=True) — LLM will overwrite existing properties …")
    registry_b.enrich_source_metadata("sqlite", recursive=True, rebuild=True)
    third_pass_calls = call_count[0] - first_pass_calls - second_pass_calls
    print(f"LLM called {third_pass_calls} additional time(s) on third pass (rebuild=True).")

    print("\nMode B complete.")


# ---------------------------------------------------------------------------
# Summary: what each property means
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Enrichment property reference")
print(DIVIDER)
properties = {
    "value_semantics":         "Semantic type of the column values (INTEGER, DATE, ENUM_CATEGORY, …)",
    "semantic_discovery":      "LLM-inferred domain subcategory and confidence score",
    "domain_concept":          "Canonical domain concept this attribute maps to",
    "interpretive_semantics":  "Human-readable interpretation of the values",
    "value_axis":              "Whether this attribute can serve as a quantitative axis",
    "quantitative_vst":        "Role in quantitative analysis (MEASUREMENT, COMPUTATIONAL, …)",
    "semantic_role":           "Structural role in the table (IDENTIFIER, EVENT_TIME, EVIDENCE, …)",
    "process_vst_role":        "Role in a process/event log (EVENT_MEASURE, STATE_VARIABLE, …)",
    "semantic_links":          "Detected statistical relationships between attribute pairs",
    "process_semantics":       "Whether the table records events; which column is the time axis",
    "process_patterns":        "Recurring patterns detected in the event data",
    "process_trends":          "Trend signals over time",
    "conditional_value_distribution": "How values distribute conditioned on other attributes",
}
for prop, description in properties.items():
    print(f"  {prop:<35} {description}")

print()
print("Demo complete.")
