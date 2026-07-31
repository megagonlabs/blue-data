"""
NL2SQL enrichment benchmark — quantitative before/after impact of blue-data.

Runs benchmark questions through three conditions and measures SQL quality:

  baseline  — raw DDL only (column names + SQL types, no enrichment)
  layer1    — DDL + all deterministic blue-data enrichment pulled from the
              live registry: semantic types, sample values, semantic roles,
              process semantics, aggregation safety, semantic links,
              value axes, process operators, derived metric candidates, …
  layer2    — layer1 + LLM-augmented enrichment: VSI refinements, SDI concept
              discovery, DCM taxonomy mapping, IVS ordering, entity/attribute
              descriptions  [enabled with --layer2]

Scoring per question (max 4 pts with --judge, max 2 pts without):
  exec_ok  (1pt) — SQL runs without error
  has_rows (1pt) — result set is non-empty
  correct  (2pt) — LLM judge confirms semantic correctness  [--judge]

Dataset : data/finance_sqlite.sql    (Czech banking, 5 tables)
Questions: data/finance_benchmark_queries.json  (15 questions targeting
           coded column values, opaque district names, process semantics)

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -e lib/ anthropic

    # baseline vs layer1 (default, no LLM enrichment cost)
    python3 examples/enrichment_benchmark.py

    # add LLM-as-judge for semantic correctness scoring
    python3 examples/enrichment_benchmark.py --judge

    # also run layer2 (LLM-augmented enrichment, more API calls)
    python3 examples/enrichment_benchmark.py --layer2 --judge

    # save full results
    python3 examples/enrichment_benchmark.py --judge --out results/run.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SQL_FILE     = Path(__file__).parent.parent / "data" / "finance_sqlite.sql"
QUERIES_FILE = Path(__file__).parent.parent / "data" / "finance_benchmark_queries.json"
DATABASE     = "finance"
TABLES       = ["district", "client", "account", "loan", "trans"]
DIV          = "=" * 72
DIV2         = "-" * 72

# ── All attribute-level properties written by MetaData enrichment ──────────
ATTR_PROPS = [
    "value_semantics",            # VSI  — semantic_type, is_identifier, numeric/temporal sub-structs
    "semantic_discovery",         # SDI  — open-world concept name + subcategory
    "domain_concept",             # DCM  — taxonomy concept mapping
    "interpretive_semantics",     # IVS  — ordinal/severity/tier ordering
    "value_axis",                 # magnitude or ordinal axis with extreme-region cutoffs
    "quantitative_vst",           # MEASUREMENT / COUNT / COMPUTATIONAL / MAGNITUDE + subtype
    "safe_aggregation",           # can_sum, can_avg, forbidden_combinations
    "semantic_role",              # IDENTIFIER / EVENT_TIME / SEGMENTATION_DRIVER / EVIDENCE / DESCRIPTIVE
    "role_query_constraints",     # can_group_by, can_filter, should_not_aggregate, …
    "process_vst_role",           # PROCESS_KEY / EVENT_TIME / EVENT_MEASURE / STATE_VARIABLE
    "time_grain_candidates",      # inferred bucketing granularities
    "conditional_value_distribution",  # P(value | group) p50/p90/p99 profiles
]

# ── All entity-level properties written by MetaData enrichment ─────────────
ENTITY_PROPS = [
    "semantic_links",             # SEGMENTS / DERIVES / SUPPORTS / ASSOCIATED between columns
    "total_component_measures",   # TOTAL/COMPONENT numeric pairs (prevents double-counting)
    "derived_metric_candidates",  # rate/ratio formulas for NL2SQL
    "process_semantics",          # EVENT row semantics + constraints
    "process_patterns",           # temporal cadence
    "process_trends",             # trend direction per measure
    "process_operators",          # AGGREGATE_OVER_TIME, CHANGE_DETECTION, CURRENT_STATE, …
    "process_query_constraints",  # requires_time_filter, latest_record_only, …
]

SYSTEM_PROMPT = """\
You are an expert SQL assistant. Convert the natural language question into a
correct, executable SQLite query.

Rules:
- Output ONLY a single SQL query inside a ```sql code block.
- Use table and column names exactly as given in the schema.
- Never hallucinate columns or tables not in the schema.
- SQLite: use strftime('%Y-%m', date_col) for month grouping.
"""

JUDGE_SYSTEM = """\
You are an expert SQL evaluator. Given a question, its expected behavior, a
generated SQL query, and its execution result, evaluate semantic correctness.

Return JSON only — no text outside:
{"verdict": "correct" | "partial" | "incorrect", "reason": "<1-2 sentences>"}

correct   — SQL fully and correctly answers the question
partial   — partially correct or minor semantic error
incorrect — wrong answer or misses the semantic requirement
"""


# ── Database ───────────────────────────────────────────────────────────────

def build_db(tmp_dir: str) -> str:
    db_path = os.path.join(tmp_dir, f"{DATABASE}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SQL_FILE.read_text())
    conn.close()
    return db_path


def run_sql(db_path: str, sql: str) -> tuple[list, str | None]:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return [], str(e)


# ── Registry ───────────────────────────────────────────────────────────────

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


# ── Context builders ───────────────────────────────────────────────────────

def _attr(reg, table, name, prop):
    return reg.get_source_database_collection_entity_attribute_property(
        DATABASE, DATABASE, "public", table, name, prop
    )


def _entity(reg, table, prop):
    return reg.get_source_database_collection_entity_property(
        DATABASE, DATABASE, "public", table, prop
    )


def _compact(obj, n=100):
    s = json.dumps(obj, default=str)
    return s[:n] + "…" if len(s) > n else s


def build_baseline_ddl(reg: DataRegistry) -> str:
    """Raw DDL — column names and SQL types only, no samples, no enrichment."""
    lines = ["-- Schema (raw DDL, no enrichment)", ""]
    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        lines.append(f"CREATE TABLE {table} (")
        lines.append(",\n".join(f"    {a['name']}" for a in attrs))
        lines.append(");\n")
    return "\n".join(lines)


def build_layer1_context(reg: DataRegistry) -> str:
    """
    Full enrichment context from the live registry — every property that
    MetaData writes, pulled directly (not hard-coded).

    Attribute properties included per column:
      VSI  value_semantics       — semantic_type, is_identifier, numeric/temporal flags
      SDI  semantic_discovery    — open-world concept + subcategory
      DCM  domain_concept        — taxonomy concept mapping
      IVS  interpretive_semantics— ordinal/severity/tier ordering
           value_axis            — axis type + extreme-region cutoffs
           quantitative_vst      — MEASUREMENT/COUNT/COMPUTATIONAL/MAGNITUDE
           safe_aggregation      — can_sum, can_avg, forbidden combinations
           semantic_role         — IDENTIFIER/EVENT_TIME/SEGMENTATION_DRIVER/…
           role_query_constraints— can_group_by, should_not_aggregate, …
           process_vst_role      — EVENT_TIME/EVENT_MEASURE/STATE_VARIABLE/…
           time_grain_candidates — daily/weekly/monthly bucketing
           conditional_value_distribution — per-group p50/p90/p99 profiles
           stats.sample_values   — actual values observed in data

    Entity properties appended as comments:
           process_semantics     — EVENT mode, event_time, aggregation constraints
           process_operators     — AGGREGATE_OVER_TIME, CHANGE_DETECTION, …
           process_query_constraints — requires_time_filter, latest_record_only, …
           process_patterns      — cadence + interval
           process_trends        — trend direction per measure
           semantic_links        — SEGMENTS/DERIVES/SUPPORTS between columns
           total_component_measures — TOTAL/COMPONENT pairs
           derived_metric_candidates — rate/ratio formulas
           description           — LLM-generated table description (Layer 2)
    """
    lines = ["-- Schema with blue-data enrichment (all registry properties)", ""]

    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        desc  = reg.get_source_database_collection_entity_description(
                    DATABASE, DATABASE, "public", table)
        lines.append(f"-- TABLE: {table}" + (f"  | {desc}" if desc else ""))
        lines.append(f"CREATE TABLE {table} (")

        col_lines = []
        for attr in attrs:
            name  = attr["name"]
            annots: list[str] = []

            # VSI — value_semantics
            vsi = _attr(reg, table, name, "value_semantics") or {}
            st  = vsi.get("semantic_type")
            if st:
                annots.append(f"type={st}")
            if vsi.get("is_identifier"):
                annots.append("identifier")
            # for ENUM_CATEGORY always show the actual values
            is_enum = st == "ENUM_CATEGORY" or vsi.get("is_categorical")
            samples = (vsi.get("examples") or
                       attr.get("properties", {}).get("stats", {}).get("sample_values", []))
            if is_enum and samples:
                annots.append(f"values=[{', '.join(str(v) for v in samples[:8])}]")
            elif samples and not is_enum:
                annots.append(f"samples={samples[:5]}")
            # temporal
            if st in ("DATE", "DATETIME") or vsi.get("temporal", {}).get("is_date"):
                g = vsi.get("temporal", {}).get("granularity")
                annots.append("temporal" + (f"[{g}]" if g else ""))
            # numeric flags
            num = vsi.get("numeric", {}) or {}
            if num.get("is_continuous"):
                annots.append("continuous")
            if num.get("is_discrete"):
                annots.append("discrete")

            # SDI — semantic_discovery
            sdi = _attr(reg, table, name, "semantic_discovery") or {}
            if sdi.get("subcategory"):
                annots.append(f"concept={sdi['subcategory']}")
            elif sdi.get("semantic_type"):
                annots.append(f"sdi_type={sdi['semantic_type']}")
            if sdi.get("rationale"):
                annots.append(f"rationale={sdi['rationale'][:70]}")

            # DCM — domain_concept
            dcm = _attr(reg, table, name, "domain_concept") or {}
            if dcm.get("concept"):
                annots.append(f"domain={dcm['concept']}")

            # IVS — interpretive_semantics
            ivs = _attr(reg, table, name, "interpretive_semantics") or {}
            if ivs.get("interpretation_type") and ivs["interpretation_type"] != "NONE":
                annots.append(f"ordering={ivs.get('ordering')}  [{ivs['interpretation_type']}]")

            # quantitative_vst
            qvst = _attr(reg, table, name, "quantitative_vst") or {}
            if qvst.get("role"):
                sub = f"[{qvst['subtype']}]" if qvst.get("subtype") else ""
                annots.append(f"qvst={qvst['role']}{sub}")

            # safe_aggregation
            sagg = _attr(reg, table, name, "safe_aggregation") or {}
            if sagg:
                parts = []
                if sagg.get("can_sum"):   parts.append("can_sum")
                if sagg.get("can_avg"):   parts.append("can_avg")
                if not sagg.get("can_sum") and not sagg.get("can_avg"):
                    parts.append("no_direct_agg")
                if sagg.get("forbidden_combinations"):
                    parts.append(f"not_with={sagg['forbidden_combinations']}")
                annots.append(f"agg=[{', '.join(parts)}]")
                for note in sagg.get("notes", []):
                    annots.append(f"agg_note={note[:60]}")

            # semantic_role
            role = _attr(reg, table, name, "semantic_role") or {}
            if role.get("primary_role"):
                annots.append(f"role={role['primary_role']}")
                segs = (role.get("role_arguments") or {}).get("segments")
                if segs:
                    annots.append(f"segments={segs}")

            # role_query_constraints
            rqc = _attr(reg, table, name, "role_query_constraints") or {}
            rqc_parts = []
            for flag, label in [
                ("can_group_by",        "group_by_ok"),
                ("can_filter",          "filter_ok"),
                ("can_order_by",        "order_by_ok"),
                ("can_aggregate",       "aggregate_ok"),
                ("should_not_aggregate","DO_NOT_AGGREGATE"),
                ("should_not_sum",      "DO_NOT_SUM"),
            ]:
                if rqc.get(flag):
                    rqc_parts.append(label)
            if rqc.get("forbidden_combinations"):
                rqc_parts.append(f"not_with={rqc['forbidden_combinations']}")
            if rqc_parts:
                annots.append(f"query=[{', '.join(rqc_parts)}]")

            # process_vst_role
            pvr = _attr(reg, table, name, "process_vst_role") or {}
            if pvr.get("process_vst_role"):
                annots.append(f"process_role={pvr['process_vst_role']}")

            # time_grain_candidates
            tgc = _attr(reg, table, name, "time_grain_candidates")
            if tgc:
                annots.append(f"time_grains={tgc}")

            # value_axis
            vax = _attr(reg, table, name, "value_axis") or {}
            if vax.get("axis_type"):
                annots.append(f"axis={vax['axis_type']}  extremes={vax.get('extreme_regions')}")

            # conditional_value_distribution
            cvd = _attr(reg, table, name, "conditional_value_distribution") or {}
            for gcol, profile in cvd.items():
                summary = {g: {"p50": v.get("p50"), "p90": v.get("p90")}
                           for g, v in list((profile.get("profiles") or {}).items())[:4]}
                annots.append(f"dist_by_{gcol}={_compact(summary)}")

            # attribute description (Layer 2)
            adesc = reg.get_source_database_collection_entity_attribute_description(
                        DATABASE, DATABASE, "public", table, name)
            if adesc:
                annots.append(f"desc={adesc[:80]}")

            line = f"    {name}"
            if annots:
                line += "  -- " + " | ".join(annots)
            col_lines.append(line)

        lines.append(",\n".join(col_lines))
        lines.append(");\n")

        # ── entity-level properties as SQL comments ──
        ps = _entity(reg, table, "process_semantics")
        if ps:
            lines.append(f"-- [process_semantics]  row_semantics={ps.get('row_semantics')}  "
                         f"event_mode={ps.get('event_mode')}  event_time={ps.get('event_time')}  "
                         f"entity_keys={ps.get('entity_keys')}")
            c = ps.get("constraints", {})
            flags = [k for k in ("requires_aggregation", "requires_temporal_reasoning",
                                 "row_local_substitution_invalid") if c.get(k)]
            if flags:
                lines.append(f"--   constraints: {', '.join(flags)}")

        ops = _entity(reg, table, "process_operators")
        if ops:
            for op in ops:
                rest = {k: v for k, v in op.items() if k not in ("operator", "rationale")}
                lines.append(f"-- [operator]  {op['operator']}: {_compact(rest)}")

        pqc = _entity(reg, table, "process_query_constraints")
        if pqc:
            for k, v in pqc.items():
                lines.append(f"-- [query_constraint]  {k}: {_compact(v)}")

        pp = _entity(reg, table, "process_patterns")
        if pp:
            lines.append(f"-- [process_pattern]  cadence={pp.get('cadence')}  "
                         f"interval_days~{pp.get('expected_interval_days')}")

        pt = _entity(reg, table, "process_trends")
        if pt and pt.get("trends"):
            for t in pt["trends"]:
                lines.append(f"-- [trend]  {t['measure']}: {t.get('trend_direction')}  "
                             f"slope={t.get('slope')}")

        links = _entity(reg, table, "semantic_links")
        if links:
            for lnk in links[:8]:
                lines.append(f"-- [link]  {lnk['source']} --[{lnk['relationship']}]→ "
                             f"{lnk['target']}  conf={lnk.get('confidence', 0):.2f}")

        tc = _entity(reg, table, "total_component_measures")
        if tc and (tc.get("totals") or tc.get("components")):
            lines.append(f"-- [total_component]  {_compact(tc)}")

        dmc = _entity(reg, table, "derived_metric_candidates")
        if dmc:
            for d in dmc[:4]:
                lines.append(f"-- [derived_metric]  {d['name']}: {d.get('formula')}  "
                             f"type={d.get('type')}")

        lines.append("")

    return "\n".join(lines)


# ── LLM wrappers ───────────────────────────────────────────────────────────

def make_chat_fn(api_key: str, model: str):
    """Returns (system, prompt) -> str for SQL generation and judging."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def call(system: str, prompt: str) -> str:
        resp = client.messages.create(
            model=model, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        for b in resp.content:
            if b.type == "text":
                return b.text
        return ""
    return call


def make_enrich_fn(api_key: str, model: str):
    """Returns prompt -> str for MetaData enricher."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model=model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        for b in resp.content:
            if b.type == "text":
                return b.text
        return ""
    return call


def extract_sql(text: str) -> str | None:
    m = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(SELECT.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def gen_sql(chat, context: str, question: str) -> str | None:
    prompt = (
        f"Schema and context:\n```\n{context}\n```\n\n"
        f"Question: {question}\n\nWrite a SQLite query."
    )
    return extract_sql(chat(SYSTEM_PROMPT, prompt))


def judge(chat, question: str, expected: str, sql: str, rows: list, err: str | None) -> dict:
    result = f"Error: {err}" if err else f"{len(rows)} rows: {rows[:2]}"
    prompt = (
        f"Question: {question}\n\nExpected: {expected}\n\n"
        f"SQL:\n```sql\n{sql or '(none)'}\n```\n\nResult: {result}\n\n"
        "Return JSON only."
    )
    try:
        raw = chat(JUDGE_SYSTEM, prompt)
        m   = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"verdict": "error", "reason": "judge failed"}


# ── Benchmark run ──────────────────────────────────────────────────────────

def run(use_judge: bool, use_layer2: bool, model: str, out_path: str | None) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set ANTHROPIC_API_KEY first.")
        return

    chat    = make_chat_fn(api_key, model)
    queries = json.loads(QUERIES_FILE.read_text())
    cats    = sorted({q["category"] for q in queries})
    n       = len(queries)

    print()
    print(DIV)
    print(f"Finance NL2SQL enrichment benchmark   model={model}")
    print(f"Questions: {n}   judge: {'yes' if use_judge else 'no'}   layer2: {'yes' if use_layer2 else 'no'}")
    print(DIV)

    tmp     = tempfile.mkdtemp(prefix="finance-bench-")
    db_path = build_db(tmp)

    # ── Build registries ───────────────────────────────────────────────────
    print("\nStep 1 — deterministic enrichment (Layer 1, no LLM cost) …")
    r1          = build_registry(tmp, llm_fn=None)
    baseline_ctx = build_baseline_ddl(r1)
    layer1_ctx   = build_layer1_context(r1)

    conditions: list[tuple[str, str]] = [
        ("baseline", baseline_ctx),
        ("layer1",   layer1_ctx),
    ]

    if use_layer2:
        print("Step 2 — LLM-augmented enrichment (Layer 2) …")
        r2         = build_registry(tmp, llm_fn=make_enrich_fn(api_key, model))
        layer2_ctx = build_layer1_context(r2)
        conditions.append(("layer2", layer2_ctx))

    cnames = [c for c, _ in conditions]
    print(f"\nContext sizes:")
    for cname, ctx in conditions:
        print(f"  {cname:<10} {len(ctx):>6} chars")

    # ── Run questions ──────────────────────────────────────────────────────
    print(f"\nRunning {n} questions × {len(conditions)} conditions …\n")
    results = []

    for i, q in enumerate(queries, 1):
        row = {
            "id":         q["id"],
            "intent":     q["intent"],
            "category":   q["category"],
            "difficulty": q.get("difficulty"),
            "target_cols": q.get("target_columns", []),
        }

        print(f"  [{i:2}/{n}] {q['id']}  [{q['category']}]")
        print(f"         {q['intent']}")

        for cname, ctx in conditions:
            sql_text  = gen_sql(chat, ctx, q["intent"])
            time.sleep(0.3)
            rows, err = run_sql(db_path, sql_text) if sql_text else ([], "no SQL generated")

            verdict_obj = None
            if use_judge:
                verdict_obj = judge(chat, q["intent"], q["expected_behavior"],
                                    sql_text or "", rows, err)
                time.sleep(0.3)

            exec_ok  = err is None
            has_rows = exec_ok and len(rows) > 0
            pts      = (1 if exec_ok else 0) + (1 if has_rows else 0)
            if verdict_obj:
                v    = verdict_obj.get("verdict", "")
                pts += 2 if v == "correct" else (1 if v == "partial" else 0)

            row[cname] = {
                "sql":       sql_text,
                "error":     err,
                "n_rows":    len(rows),
                "exec_ok":   exec_ok,
                "has_rows":  has_rows,
                "judge":     verdict_obj,
                "pts":       pts,
            }

        status_line = "  " + "  ".join(
            f"{cn}={'OK' if row[cn]['has_rows'] else ('exec' if row[cn]['exec_ok'] else 'FAIL')}"
            for cn in cnames
        )
        if use_judge:
            status_line += "  " + "  ".join(
                f"{cn}_judge={(row[cn]['judge'] or {}).get('verdict','?')}"
                for cn in cnames
            )
        print(f"  {status_line}\n")
        results.append(row)

    # ── Summary ────────────────────────────────────────────────────────────
    print(DIV)
    print("RESULTS — quantitative before / after")
    print(DIV)

    max_pts = 4 if use_judge else 2
    col_w   = 10

    def pct(num, den):
        return f"{num/den:.0%}" if den else "—"

    # Overall table
    header = f"\n{'Metric':<35}" + "".join(f"{c:>{col_w}}" for c in cnames)
    print(header)
    print(DIV2)

    for label, key in [
        ("SQL executes without error",  "exec_ok"),
        ("SQL returns non-empty result", "has_rows"),
    ]:
        row_vals = {c: sum(1 for r in results if r[c][key]) for c in cnames}
        line = f"{label:<35}"
        for c in cnames:
            line += f"{row_vals[c]:>{col_w-3}}/{n}  "
        print(line)

    if use_judge:
        for verdict, label in [("correct", "Correct"), ("partial", "Partial"), ("incorrect", "Incorrect")]:
            row_vals = {c: sum(1 for r in results
                               if (r[c]["judge"] or {}).get("verdict") == verdict)
                        for c in cnames}
            line = f"Judge — {label:<27}"
            for c in cnames:
                line += f"{row_vals[c]:>{col_w-3}}/{n}  "
            print(line)

    # Delta column (layer1 vs baseline, layer2 vs baseline)
    print()
    b_rows = sum(1 for r in results if r["baseline"]["has_rows"])
    for cname in cnames[1:]:
        c_rows = sum(1 for r in results if r[cname]["has_rows"])
        delta  = c_rows - b_rows
        print(f"  Δ has_rows  baseline → {cname}: {delta:+d}/{n}  "
              f"({pct(b_rows, n)} → {pct(c_rows, n)})")
        if use_judge:
            b_cor = sum(1 for r in results if (r["baseline"]["judge"] or {}).get("verdict") == "correct")
            c_cor = sum(1 for r in results if (r[cname]["judge"] or {}).get("verdict") == "correct")
            print(f"  Δ correct   baseline → {cname}: {c_cor - b_cor:+d}/{n}  "
                  f"({pct(b_cor, n)} → {pct(c_cor, n)})")

    # By category
    print(f"\n{'By category':<35}" + "".join(f"{c:>{col_w}}" for c in cnames))
    print(DIV2)
    for cat in cats:
        cat_r = [r for r in results if r["category"] == cat]
        nc    = len(cat_r)
        line  = f"  {cat:<33}"
        for c in cnames:
            ok   = sum(1 for r in cat_r if r[c]["has_rows"])
            line += f"{pct(ok, nc):>{col_w}}"
        print(line + f"  (n={nc})")

    # Per-question detail
    print(f"\n{'Per-question detail'}")
    print(DIV2)
    hdr = f"  {'id':<14} {'category':<24}"
    for c in cnames:
        hdr += f" {c:<6}"
    hdr += "  changes"
    print(hdr)
    print(f"  {'-'*14} {'-'*24}" + "".join(f" {'-'*6}" for _ in cnames) + "  " + "-"*30)

    for r in results:
        line   = f"  {r['id']:<14} {r['category']:<24}"
        status = {}
        for c in cnames:
            s = "OK" if r[c]["has_rows"] else ("exec" if r[c]["exec_ok"] else "FAIL")
            if use_judge:
                v = (r[c]["judge"] or {}).get("verdict", "?")
                s = f"{s}/{v[:3]}"
            status[c] = s
            line += f" {s:<6}"

        changes = []
        if "layer1" in cnames and not r["baseline"]["has_rows"] and r["layer1"]["has_rows"]:
            changes.append("L1 fixed")
        if "layer2" in cnames and not r["layer1"]["has_rows"] and r["layer2"]["has_rows"]:
            changes.append("L2 fixed")
        if "layer1" in cnames and r["baseline"]["has_rows"] and not r["layer1"]["has_rows"]:
            changes.append("L1 regressed")
        print(line + "  " + "; ".join(changes))

    # Show one example failure vs fix
    fixed = [r for r in results
             if "layer1" in cnames
             and not r["baseline"]["has_rows"]
             and r["layer1"]["has_rows"]]
    if fixed:
        ex = fixed[0]
        print(f"\n── Example: enrichment fixed '{ex['id']}' ──")
        print(f"  Q: {ex['intent']}")
        print(f"  baseline SQL : {(ex['baseline']['sql'] or '(none)')[:120]}")
        if ex["baseline"]["error"]:
            print(f"  baseline err : {ex['baseline']['error'][:80]}")
        print(f"  layer1 SQL   : {(ex['layer1']['sql'] or '(none)')[:120]}")
        print(f"  layer1 rows  : {ex['layer1']['n_rows']}")

    # Save
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "run_at":    datetime.utcnow().isoformat() + "Z",
            "model":     model,
            "use_judge": use_judge,
            "use_layer2": use_layer2,
            "n":         n,
            "conditions": cnames,
            "contexts":  {c: len(ctx) for c, ctx in conditions},
            "results":   results,
        }, indent=2))
        print(f"\nFull results saved → {out_path}")

    print()
    print("Benchmark complete.")


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Finance NL2SQL enrichment benchmark")
    p.add_argument("--judge",   action="store_true",
                   help="LLM-as-judge for semantic correctness (+2 pts per question)")
    p.add_argument("--layer2",  action="store_true",
                   help="Also run LLM-augmented enrichment (Layer 2) as a third condition")
    p.add_argument("--model",   default=os.environ.get("BLUE_DATA_LLM_MODEL", "claude-opus-4-8"))
    p.add_argument("--out",     default=None, help="Save detailed JSON results to this path")
    args = p.parse_args()
    run(use_judge=args.judge, use_layer2=args.layer2, model=args.model, out_path=args.out)


if __name__ == "__main__":
    main()
