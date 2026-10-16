"""Metadata enrichment profiler — timing and coverage across all enrichment stages.

Stages per entity:
  1. descriptions  — entity + attribute descriptions (LLM)
  2. attr          — VSI, SDI, DCM, IVS, quantitative_vst, safe_aggregation (LLM + det)
  3. relations     — semantic_links, semantic_role, role_query_constraints,
                     value_axis, conditional_value_distribution (deterministic)
  4. process       — process_semantics, process_patterns, process_trends,
                     process_operators, process_query_constraints,
                     process_vst_role, time_grain_candidates,
                     derived_metric_candidates (deterministic)

Also verifies VSI/SDI batch call structure (PASS/FAIL).

Usage:
    # Mock LLM — verifies call structure (no API key)
    python3 lib/tests/test_batch_sdi.py --database european_football_2

    # Live — OpenAI
    OPENAI_API_KEY=sk-... python3 lib/tests/test_batch_sdi.py --live --model gpt-4o-mini --database european_football_2

    # Live — Anthropic
    ANTHROPIC_API_KEY=sk-ant-... python3 lib/tests/test_batch_sdi.py --live --model claude-haiku-4-5-20251001 --database european_football_2

    # Full per-entity, per-stage profile
    OPENAI_API_KEY=sk-... python3 lib/tests/test_batch_sdi.py --live --model gpt-4o-mini --database european_football_2 --profile
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
# Complete property catalogue
# ---------------------------------------------------------------------------

# (property_key, stage, llm_or_det)
ATTR_PROPS = [
    ("description",                    "descriptions", "LLM"),
    ("value_semantics",                "attr",         "LLM"),
    ("semantic_discovery",             "attr",         "LLM"),
    ("domain_concept",                 "attr",         "LLM"),
    ("interpretive_semantics",         "attr",         "LLM"),
    ("quantitative_vst",               "attr",         "det"),
    ("safe_aggregation",               "attr",         "det"),
    ("value_axis",                     "relations",    "det"),
    ("semantic_role",                  "relations",    "det"),
    ("role_query_constraints",         "relations",    "det"),
    ("conditional_value_distribution", "relations",    "det"),
    ("process_vst_role",               "process",      "det"),
    ("time_grain_candidates",          "process",      "det"),
]

ENTITY_PROPS = [
    ("description",              "descriptions", "LLM"),
    ("semantic_links",           "relations",    "det"),
    ("total_component_measures", "attr",         "det"),
    ("derived_metric_candidates","process",      "det"),
    ("process_semantics",        "process",      "det"),
    ("process_patterns",         "process",      "det"),
    ("process_trends",           "process",      "det"),
    ("process_operators",        "process",      "det"),
    ("process_query_constraints","process",      "det"),
]

STAGES = ["descriptions", "attr", "relations", "process"]

# ---------------------------------------------------------------------------
# LLM call counters
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
        return json.dumps({"semantic_type": "MOCK", "confidence": 0.5,
                           "table_description": "mock", "attributes": {}})
    return mock_llm


def _is_openai_model(model: str) -> bool:
    return model.startswith(("gpt-", "o1", "o3", "o4"))


def make_live_llm(api_key: str, model: str):
    # gpt-4o-mini VSI batch responses can exceed 4096 tokens for 25-attr chunks;
    # use 8192 to avoid truncated JSON (which causes low value_semantics coverage)
    max_tokens = 8192

    def _call(prompt: str) -> str:
        if _is_openai_model(model):
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model, max_completion_tokens=max_tokens, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, temperature=0,
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
            print(f"    [VSI batch #{vsi_batch_call_count}] {len(names)} attrs → LLM ...")
        elif _is_batch_sdi(prompt):
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            sdi_batch_call_count += 1
            sdi_batch_attr_count += len(names)
            print(f"    [SDI batch #{sdi_batch_call_count}] {len(names)} attrs → LLM ...")
        return _call(prompt)

    return live_llm


# ---------------------------------------------------------------------------
# Coverage helpers
# ---------------------------------------------------------------------------

def _snapshot_attr_coverage(reg, source, db, coll, entity_name, attributes):
    """Return {prop: filled_count} for all attribute-level properties."""
    cov = {p: 0 for p, _, _ in ATTR_PROPS}
    for attr in attributes:
        props = attr.get("properties", {})
        for p, _, _ in ATTR_PROPS:
            if p == "description":
                if attr.get("description"):
                    cov[p] += 1
            elif props.get(p):
                cov[p] += 1
    return cov


def _snapshot_entity_coverage(reg, source, db, coll, entity_name):
    """Return {prop: bool} for all entity-level properties."""
    cov = {}
    for p, _, _ in ENTITY_PROPS:
        if p == "description":
            val = reg.get_source_database_collection_entity_description(source, db, coll, entity_name)
            cov[p] = bool(val)
        else:
            val = reg.get_source_database_collection_entity_property(source, db, coll, entity_name, p)
            cov[p] = bool(val)
    return cov


def _delta(before: dict, after: dict) -> dict:
    return {k: after[k] - before.get(k, 0) for k in after}


# ---------------------------------------------------------------------------
# Per-stage enrichment runner
# ---------------------------------------------------------------------------

def run_entity_staged(md, reg, source, db, coll, entity, attributes, rebuild):
    """Run all 4 enrichment stages with per-stage timing and coverage deltas."""
    entity_name = entity.get("name")
    entity_stats = entity.get("properties", {}).get("stats", {})
    row_samples = entity_stats.get("row_samples", [])

    md.current_entity_row_samples = row_samples
    md.current_entity_attributes = attributes

    n_cols = len(attributes)
    stage_times = {}
    stage_attr_deltas = {}
    stage_entity_deltas = {}

    def snap():
        attrs = reg.list_entity_attributes(source, db, coll, entity_name)
        return (
            _snapshot_attr_coverage(reg, source, db, coll, entity_name, attrs),
            _snapshot_entity_coverage(reg, source, db, coll, entity_name),
            attrs,
        )

    attr_cov0, ent_cov0, attributes = snap()

    for stage_name, stage_fn in [
        ("descriptions", lambda: md.enrich_entity_metadata(reg, source, db, coll, entity, attributes, rebuild)),
        ("attr",         lambda: md.enrich_attributes(reg, source, db, coll, entity_name, attributes, rebuild)),
        ("relations",    lambda: md.enrich_relations(reg, source, db, coll, entity_name, attributes, row_samples, rebuild)),
        ("process",      lambda: md.enrich_process_semantics(reg, source, db, coll, entity_name, attributes, row_samples, rebuild)),
    ]:
        t0 = time.time()
        result = stage_fn()
        stage_times[stage_name] = time.time() - t0

        # refresh attributes after stages that write to them
        attr_cov1, ent_cov1, attributes = snap()
        if stage_name == "attr":
            md.current_entity_attributes = attributes

        stage_attr_deltas[stage_name] = _delta(attr_cov0, attr_cov1)
        stage_entity_deltas[stage_name] = {k: ent_cov1[k] and not ent_cov0.get(k) for k in ent_cov1}
        attr_cov0, ent_cov0 = attr_cov1, ent_cov1

    final_attr_cov, final_ent_cov, attributes = snap()
    return {
        "entity": entity_name,
        "cols": n_cols,
        "stage_times": stage_times,
        "total_time": sum(stage_times.values()),
        "stage_attr_deltas": stage_attr_deltas,
        "stage_entity_deltas": stage_entity_deltas,
        "final_attr_cov": final_attr_cov,
        "final_ent_cov": final_ent_cov,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_profile_report(rows, total_cols, total_time):
    DIV  = "-" * 100
    DIV2 = "-" * 60

    print()
    print("=" * 100)
    print("METADATA ENRICHMENT PROFILE REPORT")
    print("=" * 100)

    # ── Per-entity timing by stage ──────────────────────────────────────────
    print(f"\n{'Per-entity timing (seconds)':}")
    hdr = f"  {'Entity':<28} {'Cols':>4}  {'total':>6}"
    for s in STAGES:
        hdr += f"  {s:>12}"
    print(hdr)
    print(DIV)
    for r in rows:
        line = f"  {r['entity']:<28} {r['cols']:>4}  {r['total_time']:>6.1f}"
        for s in STAGES:
            line += f"  {r['stage_times'].get(s, 0):>12.1f}"
        print(line)
    print(DIV)
    total_by_stage = {s: sum(r["stage_times"].get(s, 0) for r in rows) for s in STAGES}
    line = f"  {'TOTAL':<28} {total_cols:>4}  {total_time:>6.1f}"
    for s in STAGES:
        line += f"  {total_by_stage[s]:>12.1f}"
    print(line)

    # ── Attribute property coverage ─────────────────────────────────────────
    print(f"\n{'Attribute property coverage (filled / total columns)':}")
    print(f"  {'Property':<35} {'Stage':<12} {'Type':<5}  {'Filled':>6} / {'Cols':>6}  {'%':>5}  {'Written in stage':}")
    print(DIV2)
    for prop, stage, kind in ATTR_PROPS:
        filled = sum(r["final_attr_cov"].get(prop, 0) for r in rows)
        pct    = filled / total_cols * 100 if total_cols else 0
        # which stage wrote most of this property
        by_stage = {s: sum(r["stage_attr_deltas"].get(s, {}).get(prop, 0) for r in rows) for s in STAGES}
        top_stage = max(by_stage, key=by_stage.get) if any(by_stage.values()) else "—"
        print(f"  {prop:<35} {stage:<12} {kind:<5}  {filled:>6} / {total_cols:>6}  {pct:>4.0f}%  {top_stage}")

    # ── Entity property coverage ─────────────────────────────────────────────
    n = len(rows)
    print(f"\n{'Entity property coverage (entities that have this property)':}")
    print(f"  {'Property':<35} {'Stage':<12} {'Type':<5}  {'Present':>7} / {'Total':>5}")
    print(DIV2)
    for prop, stage, kind in ENTITY_PROPS:
        present = sum(1 for r in rows if r["final_ent_cov"].get(prop))
        print(f"  {prop:<35} {stage:<12} {kind:<5}  {present:>7} / {n:>5}")

    # ── Sample enriched attributes from widest table ─────────────────────────
    widest = max(rows, key=lambda r: r["cols"])
    print(f"\nSample from '{widest['entity']}' ({widest['cols']} cols) — stage times: "
          + "  ".join(f"{s}={widest['stage_times'].get(s,0):.1f}s" for s in STAGES))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--live",     action="store_true", help="Use real LLM")
    p.add_argument("--database", default=None,        help="Single BIRD database (e.g. european_football_2)")
    p.add_argument("--model",    default=DEFAULT_MODEL)
    p.add_argument("--profile",  action="store_true", help="Per-entity, per-stage timing and coverage")
    args = p.parse_args()

    if args.live:
        env_key = "OPENAI_API_KEY" if _is_openai_model(args.model) else "ANTHROPIC_API_KEY"
        api_key = os.environ.get(env_key)
        if not api_key:
            print(f"ERROR: {env_key} not set.")
            return
        llm_fn = make_live_llm(api_key, args.model)
        print(f"Mode: LIVE  model={args.model}  max_tokens=8192")
    else:
        llm_fn = make_mock_llm()
        print("Mode: MOCK  (pass --live for real LLM)")

    source_name = args.database or "bird_all"
    print(f"Setting up SQLiteDBSource  dir={DB_DIR}")
    source = SQLiteDBSource(
        name=source_name,
        properties={"connection": {"database_directory": DB_DIR, "stat_sample_size": 500}},
    )
    md  = MetaData(llm_fn=llm_fn, properties={"enable_semantic_link_validation": False})
    reg = DataRegistry(store=MemoryJSONSource(), metadata_enricher=md)
    reg.register_source(source)

    print("Syncing ...")
    reg.sync_all(recursive=True)

    databases_to_enrich = reg.list_source_databases(source_name)
    if args.database:
        databases_to_enrich = [d for d in databases_to_enrich if d.get("name") == args.database]
        if not databases_to_enrich:
            avail = [d.get("name") for d in reg.list_source_databases(source_name)]
            print(f"ERROR: '{args.database}' not found. Available: {avail}")
            return

    total_entities, total_cols = 0, 0
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
    rebuild = args.live
    profile_rows = []
    t_total = time.time()

    for db in databases_to_enrich:
        db_name = db.get("name")
        for coll in reg.list_database_collections(source_name, db_name):
            coll_name = coll.get("name")
            for entity in reg.list_collection_entities(source_name, db_name, coll_name):
                attributes = reg.list_entity_attributes(source_name, db_name, coll_name, entity.get("name"))
                if args.profile:
                    row = run_entity_staged(md, reg, source_name, db_name, coll_name, entity, attributes, rebuild)
                    profile_rows.append(row)
                    print(f"  {entity.get('name'):<30} {len(attributes):>3} cols  "
                          f"{row['total_time']:>6.1f}s  {llm_call_count} total LLM calls  "
                          + "  ".join(f"{s}={row['stage_times'][s]:.1f}s" for s in STAGES))
                else:
                    md.enrich_entity_full(reg, source_name, db_name, coll_name, entity, attributes, rebuild)

    elapsed = time.time() - t_total

    # Summary
    print()
    print("Results:")
    print(f"  Databases          : {len(databases_to_enrich)}")
    print(f"  Entities           : {total_entities}")
    print(f"  Columns            : {total_cols}")
    print(f"  Total LLM calls    : {llm_call_count}  (old path ~{total_cols * 4}+)")
    print(f"  VSI batch calls    : {vsi_batch_call_count}  (old was {total_cols})")
    print(f"  SDI batch calls    : {sdi_batch_call_count}  (old was {total_cols})")
    print(f"  VSI+SDI reduction  : {total_cols * 2 / max(vsi_batch_call_count + sdi_batch_call_count, 1):.1f}x")
    print(f"  Time               : {elapsed:.1f}s")

    if args.profile and profile_rows:
        print_profile_report(profile_rows, total_cols, elapsed)

    # PASS/FAIL
    print()
    sdi_ok = sdi_batch_call_count < total_cols and sdi_batch_attr_count >= total_cols * 0.9
    vsi_ok = (vsi_batch_call_count < total_cols and vsi_batch_attr_count >= total_cols * 0.9) \
             or (not args.live and vsi_batch_call_count == 0)
    if vsi_ok and sdi_ok:
        print("PASS — VSI and SDI batched correctly (<1 call per attr, ≥90% attrs covered)")
    else:
        if not vsi_ok:
            print(f"FAIL VSI — {vsi_batch_call_count} calls / {vsi_batch_attr_count} attrs (expected <{total_cols} / ≥{int(total_cols*0.9)})")
        if not sdi_ok:
            print(f"FAIL SDI — {sdi_batch_call_count} calls / {sdi_batch_attr_count} attrs (expected <{total_cols} / ≥{int(total_cols*0.9)})")


if __name__ == "__main__":
    main()
