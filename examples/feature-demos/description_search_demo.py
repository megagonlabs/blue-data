"""
Demo 2 — Description-Enriched Data Discovery
==============================================
Problem : Column names like 'freight', 'units_in_stock', 'discontinued',
          'hire_date' don't tell analysts what they mean. Searching
          "shipping cost" or "no longer sold" returns nothing.
Solution: blue-data Layer 2 generates attribute descriptions from data
          context. Registry search then finds columns by semantic meaning.

Descriptions are generated once by blue-data Layer 2 and saved to
data/northwind_descriptions.json — committed so the demo runs instantly
with zero API calls at demo time.

Usage:
    # Generate descriptions (one-time, saves to data/northwind_descriptions.json)
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/description_search_demo.py --generate

    # Run demo (zero API key — loads pre-generated descriptions)
    python3 examples/description_search_demo.py
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SQL_FILE  = Path(__file__).parent.parent.parent / "data" / "northwind_sqlite.sql"
DESC_FILE = Path(__file__).parent.parent.parent / "data" / "northwind_descriptions.json"
DATABASE  = "northwind"
TABLES    = ["categories", "customers", "employees", "products",
             "orders", "order_details", "suppliers"]
DIV       = "=" * 68
DIV2      = "-" * 68

# Intent queries that describe meaning — no word appears in any column name
SEARCH_QUERIES = [
    {
        "query":  "shipping cost",
        "wants":  ["orders.freight"],
        "why":    "'freight' doesn't contain 'shipping' or 'cost'",
    },
    {
        "query":  "current inventory",
        "wants":  ["products.units_in_stock"],
        "why":    "'units_in_stock' doesn't contain 'inventory'",
    },
    {
        "query":  "job position",
        "wants":  ["employees.title"],
        "why":    "'title' doesn't contain 'job' or 'position'",
    },
    {
        "query":  "when order placed",
        "wants":  ["orders.order_date"],
        "why":    "'order_date' doesn't contain 'placed' or 'when'",
    },
]

STOPWORDS = {"a", "an", "the", "is", "in", "of", "for", "to", "and", "or", "at"}


# ── Infrastructure ─────────────────────────────────────────────────────────

def build_db(tmp_dir: str) -> str:
    import sqlite3
    db_path = os.path.join(tmp_dir, f"{DATABASE}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SQL_FILE.read_text())
    conn.close()
    return db_path


def build_registry(db_dir: str, llm_fn=None) -> DataRegistry:
    source = SQLiteDBSource(
        name=DATABASE,
        properties={"connection": {"database_directory": db_dir}},
    )
    reg = DataRegistry(store=MemoryJSONSource(), metadata_enricher=MetaData(llm_fn=llm_fn))
    reg.register_source(source)
    reg.sync_all(recursive=True)
    reg.collect_source_stats(DATABASE, recursive=True)
    reg.enrich_source_metadata(DATABASE, recursive=True, rebuild=False)
    return reg


def make_enrich_fn(api_key: str, model: str):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model=model, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        for b in resp.content:
            if b.type == "text":
                return b.text
        return ""
    return call


def inject_descriptions(reg: DataRegistry, descriptions: dict) -> None:
    for key, desc in descriptions.items():
        if "." not in key:
            continue
        table, col = key.split(".", 1)
        try:
            reg.set_source_database_collection_entity_attribute_description(
                DATABASE, DATABASE, "public", table, col, desc
            )
        except Exception:
            pass


# ── Word-level search ──────────────────────────────────────────────────────
# The registry KeywordSearch does exact-phrase substring matching.
# For the demo we use word-level scoring so "shipping cost" finds a column
# whose description contains "shipping" and "cost" even in different positions.

def word_search(reg: DataRegistry, query: str, top_k: int = 5) -> list[tuple[str, float, str]]:
    """
    Returns list of (table.col, score, matched_description) sorted by score desc.
    Score = fraction of non-stopword query words found in name + description.
    """
    words = [w for w in query.lower().split() if w not in STOPWORDS and len(w) > 2]
    if not words:
        return []

    results = []
    for rec in reg.list_records():
        if rec.get("type") != "attribute":
            continue
        name  = rec.get("name", "").lower()
        desc  = (rec.get("description") or "").lower()
        scope = rec.get("scope", "")
        table = scope.strip("/").split("/")[-1]
        text  = name + " " + desc

        matched = [w for w in words if w in text]
        if not matched:
            continue

        score = len(matched) / len(words)
        results.append((f"{table}.{name}", score, rec.get("description") or ""))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ── Generate mode ──────────────────────────────────────────────────────────

def generate_and_save(model: str) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set ANTHROPIC_API_KEY to use --generate.")
        return

    print(f"\nGenerating Northwind descriptions with {model}…")
    tmp = tempfile.mkdtemp(prefix="desc-gen-")
    build_db(tmp)
    reg = build_registry(tmp, llm_fn=make_enrich_fn(api_key, model))

    descriptions = {}
    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        for attr in attrs:
            name = attr["name"]
            desc = reg.get_source_database_collection_entity_attribute_description(
                DATABASE, DATABASE, "public", table, name
            )
            if desc:
                descriptions[f"{table}.{name}"] = desc

    payload = {
        "generated_by": f"blue-data Layer 2 ({model})",
        "database":     DATABASE,
        "descriptions": descriptions,
    }
    DESC_FILE.write_text(json.dumps(payload, indent=2))
    print(f"\nSaved {len(descriptions)} descriptions → {DESC_FILE}")
    print("\nSample descriptions generated:")
    targets = [sq["wants"][0] for sq in SEARCH_QUERIES]
    for key in targets:
        if key in descriptions:
            print(f"  {key:<35}  \"{descriptions[key][:60]}\"")
    print("\nCommit data/northwind_descriptions.json so the demo runs without API calls.")


# ── Demo mode ──────────────────────────────────────────────────────────────

def run_demo() -> None:
    if not DESC_FILE.exists():
        print(f"\nERROR: {DESC_FILE} not found.")
        print("Run once to generate descriptions:")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        print("  python3 examples/description_search_demo.py --generate")
        return

    meta         = json.loads(DESC_FILE.read_text())
    descriptions = meta.get("descriptions", {})
    generated_by = meta.get("generated_by", "blue-data Layer 2")

    print()
    print(DIV)
    print("Demo 2 — Description-Enriched Data Discovery")
    print(DIV)
    print()
    print("  Problem : Column names like 'freight', 'units_in_stock',")
    print("            'title', 'order_date' hide their meaning.")
    print("            Analysts searching 'shipping cost' find nothing.")
    print("  Solution: blue-data Layer 2 generates descriptions once.")
    print("            Registry search then finds columns by meaning.")
    print()
    print(f"  Descriptions: pre-generated by {generated_by}")
    print(f"  API calls at demo runtime: 0")

    tmp = tempfile.mkdtemp(prefix="desc-demo-")
    build_db(tmp)
    reg = build_registry(tmp, llm_fn=None)

    # ── Before: no descriptions ────────────────────────────────────────────
    print()
    print(DIV2)
    print("Before — search on column names only  (no descriptions)")
    print(DIV2)
    print()

    before_hits: dict[str, list] = {}
    for sq in SEARCH_QUERIES:
        hits = word_search(reg, sq["query"])
        before_hits[sq["query"]] = [col for col, _, _ in hits]
        found = any(w in before_hits[sq["query"]] for w in sq["wants"])
        mark  = "✓" if found else "✗"
        print(f"  search: \"{sq['query']}\"")
        print(f"    {mark}  hits: {before_hits[sq['query']][:3] or '(none)'}")
        print(f"         {sq['why']}")

    before_score = sum(
        1 for sq in SEARCH_QUERIES
        if any(w in before_hits[sq["query"]] for w in sq["wants"])
    )

    # ── Inject descriptions ────────────────────────────────────────────────
    print()
    print(DIV2)
    print("Layer 2 descriptions generated by blue-data (loaded from file)")
    print(DIV2)
    print()

    targets = [sq["wants"][0] for sq in SEARCH_QUERIES]
    for key in targets:
        desc = descriptions.get(key, "")
        if desc:
            print(f"  {key:<35}  \"{desc[:60]}\"")
        else:
            print(f"  {key:<35}  (no description generated)")

    inject_descriptions(reg, descriptions)

    # ── After: search with descriptions ───────────────────────────────────
    print()
    print(DIV2)
    print("After — search on column names + Layer 2 descriptions")
    print(DIV2)
    print()

    after_hits: dict[str, list] = {}
    for sq in SEARCH_QUERIES:
        hits = word_search(reg, sq["query"])
        after_hits[sq["query"]] = [col for col, _, _ in hits]
        found  = any(w in after_hits[sq["query"]] for w in sq["wants"])
        mark   = "✓" if found else "✗"
        was_found = any(w in before_hits[sq["query"]] for w in sq["wants"])
        print(f"  search: \"{sq['query']}\"")
        print(f"    {mark}  hits: {after_hits[sq['query']][:3] or '(none)'}")
        if not was_found and found:
            desc_snippet = descriptions.get(sq["wants"][0], "")[:55]
            print(f"         ↑ surfaced via description: \"{desc_snippet}\"")

    after_score = sum(
        1 for sq in SEARCH_QUERIES
        if any(w in after_hits[sq["query"]] for w in sq["wants"])
    )

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print(DIV)
    print("Result")
    print(DIV)
    print()
    n = len(SEARCH_QUERIES)
    print(f"  without descriptions  {before_score}/{n}  (column name match only)")
    print(f"  with descriptions     {after_score}/{n}  (semantic meaning match)")
    print()
    print("  Layer 2 generates descriptions once — enriches the registry")
    print("  permanently. No API calls at search time.")
    print()


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generate", action="store_true",
                   help="Run Layer 2 enrichment and save descriptions to data/northwind_descriptions.json")
    p.add_argument("--model",
                   default=os.environ.get("BLUE_DATA_LLM_MODEL", "claude-haiku-4-5-20251001"))
    args = p.parse_args()

    if args.generate:
        generate_and_save(args.model)
    else:
        run_demo()


if __name__ == "__main__":
    main()
