"""
Finance dataset enrichment demo.

Shows how blue-data enrichment resolves ambiguity in a realistic financial
database — the Czech banking dataset (BIRD benchmark).  Column names like
k_symbol, operation, type in the trans table and a2-a16 in the district
table carry no meaning from their names alone.  Enrichment surfaces what
they actually are.

Two enrichment layers:

  Layer 1 — Deterministic (no LLM, no API key)
    Detects DATE, ENUM_CATEGORY, INTEGER, FLOAT from value patterns.
    Identifies EVENT_TIME, SEGMENTATION_DRIVER, EVIDENCE semantic roles.
    Detects process semantics: trans is an event log.

  Layer 2 — LLM-augmented (set ANTHROPIC_API_KEY or OPENAI_API_KEY)
    Resolves INTEGER → CURRENCY_AMOUNT for amount, balance, district salary.
    Resolves INTEGER → DURATION for loan.duration.
    Interprets ENUM_CATEGORY codes: what do A/B/C/D mean in loan.status?
    Maps k_symbol, operation, type to domain concepts.

Run:
    pip install -e lib/
    python3 examples/finance_demo.py

For LLM enrichment:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/finance_demo.py
"""

import os
import sqlite3
import tempfile
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DIVIDER = "=" * 64
SQL_FILE = Path(__file__).parent.parent / "data" / "finance_sqlite.sql"

TABLES   = ["district", "client", "account", "loan", "trans"]
DATABASE = "finance"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _build_db(tmp_dir: str) -> str:
    """Create the finance SQLite database and return the db directory."""
    db_path = os.path.join(tmp_dir, f"{DATABASE}.db")
    sql = SQL_FILE.read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.close()
    return tmp_dir


def _build_registry(db_dir: str, metadata_enricher=None) -> DataRegistry:
    source = SQLiteDBSource(
        name="finance",
        properties={"connection": {"database_directory": db_dir}},
    )
    registry = DataRegistry(
        store=MemoryJSONSource(),
        metadata_enricher=metadata_enricher,
    )
    registry.register_source(source)
    return registry


def _run_pipeline(registry: DataRegistry) -> None:
    """sync → stats → enrich (must be called in this order)."""
    registry.sync_all(recursive=True)
    registry.collect_source_stats("finance", recursive=True)
    registry.enrich_source_metadata("finance", recursive=True, rebuild=False)


def _print_table(registry: DataRegistry, entity: str) -> None:
    """Print enrichment results for every attribute of an entity."""
    attrs = registry.list_entity_attributes("finance", DATABASE, "public", entity)
    print(f"\n  {entity}")
    print(f"  {'attribute':<22} {'semantic_type':<22} {'role':<22} {'qvst_role'}")
    print(f"  {'-'*22} {'-'*22} {'-'*22} {'-'*12}")
    for attr in attrs:
        name = attr["name"]
        vsi  = registry.get_source_database_collection_entity_attribute_property(
                   "finance", DATABASE, "public", entity, name, "value_semantics") or {}
        role = registry.get_source_database_collection_entity_attribute_property(
                   "finance", DATABASE, "public", entity, name, "semantic_role") or {}
        qvst = registry.get_source_database_collection_entity_attribute_property(
                   "finance", DATABASE, "public", entity, name, "quantitative_vst") or {}
        print(f"  {name:<22} {vsi.get('semantic_type','—'):<22} "
              f"{role.get('primary_role','—'):<22} {qvst.get('role','—')}")


# ---------------------------------------------------------------------------
# Layer 1 — Deterministic enrichment
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("LAYER 1 — Deterministic enrichment  (no LLM)")
print(DIVIDER)

tmp_a = tempfile.mkdtemp(prefix="finance-demo-a-")
_build_db(tmp_a)
registry_a = _build_registry(tmp_a, metadata_enricher=MetaData(llm_fn=None))
_run_pipeline(registry_a)

print("\nWhat deterministic enrichment resolves:")
for table in TABLES:
    _print_table(registry_a, table)

# Process semantics on trans
ps = registry_a.get_source_database_collection_entity_property(
    "finance", DATABASE, "public", "trans", "process_semantics"
)
if ps:
    print(f"\n  trans process semantics detected:")
    print(f"    row_semantics = {ps.get('row_semantics')}")
    print(f"    event_time    = {ps.get('event_time')}")
    print(f"    event_key     = {ps.get('event_key')}")

# Semantic links
links = registry_a.get_source_database_collection_entity_property(
    "finance", DATABASE, "public", "trans", "semantic_links"
)
if links:
    print(f"\n  trans semantic links ({len(links)} detected):")
    for lnk in links[:4]:
        print(f"    {lnk['source']} → {lnk['target']}  "
              f"({lnk.get('relationship','?')}, confidence={lnk.get('confidence',0):.2f})")

print("\n  What's still unresolved after Layer 1:")
print("    district.a2–a16   — opaque column names, types only (INTEGER/STRING/FLOAT)")
print("    trans.amount      — INTEGER (is it a count or a currency amount?)")
print("    trans.balance     — INTEGER (same ambiguity)")
print("    trans.k_symbol    — STRING (7 Czech category codes: UVER, SIPO, POJISTNE…")
print("                        deterministic can't confirm they're a closed set,")
print("                        and can't explain what each code means)")
print("    loan.duration     — INTEGER (months? days? years?)")
print("    loan.status       — ENUM_CATEGORY (A/B/C/D detected, but meaning unknown)")
print("    district.a11      — INTEGER (average salary in CZK, indistinguishable from a count)")

print("\nLayer 1 complete — no LLM was called.")


# ---------------------------------------------------------------------------
# Layer 2 — LLM-augmented enrichment
# ---------------------------------------------------------------------------

def _build_llm_fn():
    """Build llm_fn from whichever API key is available. Returns None if neither set."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key    = os.environ.get("OPENAI_API_KEY")

    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        model  = os.environ.get("BLUE_DATA_LLM_MODEL", "claude-opus-4-8")

        def llm_fn(prompt: str) -> str:
            resp = client.messages.create(
                model=model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            for block in resp.content:
                if block.type == "text":
                    return block.text
            return ""
        print(f"  Using Anthropic ({model})")
        return llm_fn

    if openai_key:
        import openai
        client = openai.OpenAI(api_key=openai_key)
        model  = os.environ.get("BLUE_DATA_LLM_MODEL", "gpt-4o")

        def llm_fn(prompt: str) -> str:
            resp = client.chat.completions.create(
                model=model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""
        print(f"  Using OpenAI ({model})")
        return llm_fn

    return None


print()
print(DIVIDER)
print("LAYER 2 — LLM-augmented enrichment")
print(DIVIDER)

llm_fn = _build_llm_fn()

if llm_fn is None:
    print("\n  SKIPPED — set ANTHROPIC_API_KEY or OPENAI_API_KEY to run Layer 2.")
    print("  Install: pip install anthropic   or   pip install openai")
else:
    call_count = [0]

    def counted_llm_fn(prompt: str) -> str:
        call_count[0] += 1
        return llm_fn(prompt)

    tmp_b = tempfile.mkdtemp(prefix="finance-demo-b-")
    _build_db(tmp_b)
    registry_b = _build_registry(tmp_b, metadata_enricher=MetaData(llm_fn=counted_llm_fn))
    _run_pipeline(registry_b)

    print(f"\n  LLM called {call_count[0]} time(s) across all tables.")
    print("\nWhat LLM enrichment adds:")
    for table in TABLES:
        _print_table(registry_b, table)

    # Show the specific resolutions that matter
    print("\n  Key resolutions from LLM enrichment:")

    focus = {
        ("trans",    "amount"):   "value_semantics",
        ("trans",    "balance"):  "value_semantics",
        ("trans",    "k_symbol"): "value_semantics",
        ("loan",     "duration"): "value_semantics",
        ("loan",     "status"):   "value_semantics",
        ("district", "a11"):      "value_semantics",
        ("district", "a2"):       "semantic_discovery",
    }

    for (entity, attr), prop in focus.items():
        val = registry_b.get_source_database_collection_entity_attribute_property(
            "finance", DATABASE, "public", entity, attr, prop
        )
        if val:
            if prop == "value_semantics":
                detail = val.get("semantic_type", "—")
            elif prop == "semantic_discovery":
                detail = val.get("subcategory", val.get("description", "—"))
            elif prop == "interpretive_semantics":
                detail = val.get("interpretation", val.get("description", "—"))
            else:
                detail = str(val)
            print(f"    {entity}.{attr:<18} {prop}: {detail}")

    # Auto-generated entity descriptions
    print("\n  Auto-generated entity descriptions:")
    for table in ["trans", "loan", "district"]:
        desc = registry_b.get_source_database_collection_entity_description(
            "finance", DATABASE, "public", table
        )
        if desc:
            print(f"    {table}: {desc[:120]}{'...' if len(desc) > 120 else ''}")

    print("\nLayer 2 complete.")


# ---------------------------------------------------------------------------
# Registry search — works with Layer 1 output
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("Registry search after enrichment")
print(DIVIDER)

for query in [
    "transaction amount and balance",
    "loan status and duration",
    "date columns",
]:
    hits = registry_a.search_records(query, type="attribute")
    names = [f"{h.get('scope','').split('/')[-1]}.{h['name']}" for h in hits[:4]]
    print(f"\n  search: '{query}'")
    print(f"  top hits: {names}")

print()
print("Demo complete.")
