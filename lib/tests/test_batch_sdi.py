"""Smoke-test for batch SDI on BIRD databases.

Usage:
    # Mock LLM — verifies call structure only (no API key needed)
    python3 test_batch_sdi.py

    # Real LLM — Anthropic
    ANTHROPIC_API_KEY=sk-ant-... python3 test_batch_sdi.py --live --model claude-haiku-4-5-20251001

    # Real LLM — OpenAI
    OPENAI_API_KEY=sk-... python3 test_batch_sdi.py --live --model gpt-4o-mini

    # Single database only
    ANTHROPIC_API_KEY=sk-ant-... python3 test_batch_sdi.py --live --database european_football_2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

DB_DIR = "data/bird"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

llm_call_count = 0
vsi_batch_call_count = 0
vsi_batch_attr_count = 0
sdi_batch_call_count = 0
sdi_batch_attr_count = 0


def _is_batch_vsi(prompt: str) -> bool:
    return (
        '"name":' in prompt
        and "ATTRIBUTES:" in prompt
        and "Return a single JSON object mapping" in prompt
        and "ALLOWED_SEMANTIC_TYPES" in prompt
    )


def _is_batch_sdi(prompt: str) -> bool:
    return (
        '"name":' in prompt
        and "ATTRIBUTES:" in prompt
        and "Return a single JSON object mapping" in prompt
        and "THREE-LAYER SEMANTIC MODEL" in prompt
    )


def make_mock_llm():
    def mock_llm(prompt: str) -> str:
        global llm_call_count, vsi_batch_call_count, vsi_batch_attr_count, sdi_batch_call_count, sdi_batch_attr_count
        llm_call_count += 1
        if _is_batch_vsi(prompt):
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            vsi_batch_call_count += 1
            vsi_batch_attr_count += len(names)
            return json.dumps({
                name: {"primary_type": "MOCK", "semantic_type": "MOCK", "is_categorical": False,
                       "is_identifier": False, "is_free_text": False, "confidence": 0.5,
                       "numeric": {}, "temporal": {}, "normalization": {}, "examples_used": [], "notes": []}
                for name in names
            })
        if _is_batch_sdi(prompt):
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            sdi_batch_call_count += 1
            sdi_batch_attr_count += len(names)
            return json.dumps({
                name: {"semantic_type": "MOCK", "subcategory": None, "confidence": 0.5,
                       "range": {"min": None, "max": None}, "criteria": None, "rationale": "mock", "examples": []}
                for name in names
            })
        return json.dumps({"semantic_type": "MOCK", "confidence": 0.5})
    return mock_llm


def _is_openai_model(model: str) -> bool:
    return model.startswith(("gpt-", "o1", "o3", "o4"))


def make_live_llm(api_key: str, model: str):
    def _call(prompt: str) -> str:
        if _is_openai_model(model):
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model, max_tokens=4096, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model, max_tokens=4096, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return next((b.text for b in resp.content if b.type == "text"), "")

    def live_llm(prompt: str) -> str:
        global llm_call_count, vsi_batch_call_count, vsi_batch_attr_count, sdi_batch_call_count, sdi_batch_attr_count
        llm_call_count += 1
        if _is_batch_vsi(prompt):
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            vsi_batch_call_count += 1
            vsi_batch_attr_count += len(names)
            print(f"    [VSI batch #{vsi_batch_call_count}] {len(names)} attrs → calling LLM ...")
        elif _is_batch_sdi(prompt):
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            sdi_batch_call_count += 1
            sdi_batch_attr_count += len(names)
            print(f"    [SDI batch #{sdi_batch_call_count}] {len(names)} attrs → calling LLM ...")
        return _call(prompt)

    return live_llm


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global llm_call_count, sdi_batch_call_count, sdi_batch_attr_count

    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true", help="Use real LLM (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)")
    p.add_argument("--database", default=None, help="Restrict to a single BIRD database name (e.g. european_football_2)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL}; use gpt-4o-mini for OpenAI)")
    args = p.parse_args()

    if args.live:
        if _is_openai_model(args.model):
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("ERROR: OPENAI_API_KEY not set.")
                return
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print("ERROR: ANTHROPIC_API_KEY not set.")
                return
        llm_fn = make_live_llm(api_key, args.model)
        print(f"Mode: LIVE  model={args.model}")
    else:
        llm_fn = make_mock_llm()
        print("Mode: MOCK  (pass --live to use real LLM)")

    source_name = args.database or "bird_all"
    db_dir = DB_DIR

    # If --database given, only that one .sqlite file is in scope by pointing to
    # a sub-source. We still use the same directory but filter after sync.
    print(f"Setting up SQLiteDBSource  dir={db_dir}")
    source = SQLiteDBSource(
        name=source_name,
        properties={"connection": {"database_directory": db_dir, "stat_sample_size": 500}},
    )

    md = MetaData(
        llm_fn=llm_fn,
        properties={"enable_semantic_link_validation": False},
    )
    reg = DataRegistry(store=MemoryJSONSource(), metadata_enricher=md)
    reg.register_source(source)

    print("Syncing ...")
    reg.sync_all(recursive=True)

    # If --database, only enrich that one DB
    databases_to_enrich = reg.list_source_databases(source_name)
    if args.database:
        databases_to_enrich = [d for d in databases_to_enrich if d.get("name") == args.database]
        if not databases_to_enrich:
            available = [d.get("name") for d in reg.list_source_databases(source_name)]
            print(f"ERROR: database '{args.database}' not found. Available: {available}")
            return

    # Count total columns in scope
    total_entities = 0
    total_cols = 0
    for db in databases_to_enrich:
        for coll in reg.list_database_collections(source_name, db.get("name")):
            for e in reg.list_collection_entities(source_name, db.get("name"), coll.get("name")):
                total_entities += 1
                total_cols += len(reg.list_entity_attributes(source_name, db.get("name"), coll.get("name"), e.get("name")))

    print(f"Collecting stats  ({len(databases_to_enrich)} DB(s), {total_entities} entities, {total_cols} cols) ...")
    t0 = time.time()
    reg.collect_source_stats(source_name, recursive=True)
    print(f"  stats done in {time.time() - t0:.1f}s")

    print("Running metadata enrichment ...")
    global llm_call_count, vsi_batch_call_count, vsi_batch_attr_count, sdi_batch_call_count, sdi_batch_attr_count
    llm_call_count = vsi_batch_call_count = vsi_batch_attr_count = sdi_batch_call_count = sdi_batch_attr_count = 0
    t0 = time.time()
    rebuild = args.live  # live mode uses rebuild=True so VSI/SDI actually fire despite deterministic pre-fill
    for db in databases_to_enrich:
        md.collect_source_database_metadata(reg, source_name, db.get("name"), recursive=True, rebuild=rebuild)
    elapsed = time.time() - t0

    # Spot-check Match table if present
    match_sdi_info = ""
    try:
        match_attrs = reg.list_entity_attributes(source_name, "european_football_2", "public", "Match")
        if match_attrs:
            covered = sum(1 for a in match_attrs if a.get("properties", {}).get("semantic_discovery"))
            match_sdi_info = f"\n  Match SDI          : {covered}/{len(match_attrs)} attributes enriched"
            if args.live and covered > 0:
                # Show a few real results
                samples = [(a["name"], a["properties"]["semantic_discovery"])
                           for a in match_attrs if a.get("properties", {}).get("semantic_discovery")][:3]
                match_sdi_info += "\n  Match SDI samples  :"
                for name, sdi in samples:
                    match_sdi_info += f"\n    {name}: {sdi.get('semantic_type')} / {sdi.get('subcategory')} — {sdi.get('rationale', '')[:60]}"
    except Exception:
        pass

    print()
    print("Results:")
    print(f"  Databases          : {len(databases_to_enrich)}")
    print(f"  Entities           : {total_entities}")
    print(f"  Columns            : {total_cols}")
    print(f"  Total LLM calls    : {llm_call_count}  (old path ~{total_cols * 4}+)")
    print(f"  VSI batch calls    : {vsi_batch_call_count}  (one per entity — old was {total_cols})")
    print(f"  VSI attrs covered  : {vsi_batch_attr_count}")
    print(f"  SDI batch calls    : {sdi_batch_call_count}  (one per entity — old was {total_cols})")
    print(f"  SDI attrs covered  : {sdi_batch_attr_count}")
    print(f"  VSI+SDI reduction  : {total_cols * 2 / max(vsi_batch_call_count + sdi_batch_call_count, 1):.1f}x")
    print(f"  Time               : {elapsed:.1f}s")
    print(match_sdi_info)

    print()
    # PASS: calls << total_cols (batching working) and ≥90% attrs covered.
    # VSI only fires when rebuild=True (live mode); rebuild=False skips it because the
    # deterministic pre-fill already set value_semantics — 0 VSI calls is correct there.
    sdi_ok = sdi_batch_call_count < total_cols and sdi_batch_attr_count >= total_cols * 0.9
    vsi_ok = (vsi_batch_call_count < total_cols and vsi_batch_attr_count >= total_cols * 0.9) \
             or (not args.live and vsi_batch_call_count == 0)

    if vsi_ok and sdi_ok:
        print("PASS — VSI and SDI both batched correctly (<1 call per attr, ≥90% attrs covered)")
    else:
        if not vsi_ok:
            print(f"FAIL VSI — {vsi_batch_call_count} calls covering {vsi_batch_attr_count} attrs "
                  f"(expected <{total_cols} calls, ≥{int(total_cols*0.9)} attrs)")
        if not sdi_ok:
            print(f"FAIL SDI — {sdi_batch_call_count} calls covering {sdi_batch_attr_count} attrs "
                  f"(expected <{total_cols} calls, ≥{int(total_cols*0.9)} attrs)")


if __name__ == "__main__":
    main()
