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
Questions: data/finance_benchmark_queries.json  (24 questions across 7 categories)

Question categories — each tests a distinct enrichment feature:

  none (4 Qs)
    Control questions answerable from column names alone. Expected: both
    baseline and layer1 correct. Validates benchmark honesty.

  enum_coded_value (6 Qs)
    Columns store Czech codes that Haiku cannot guess from English intent:
      trans.operation: VKLAD=cash deposit, VYBER=withdrawal,
                       PREVOD NA UCET=outgoing wire
      trans.k_symbol:  POJISTNE=insurance, DUCHOD=pension, SIPO=utilities, UROK=interest
    At baseline: Haiku generates WHERE operation='DEPOSIT' → 0 rows (wrong code).
    Layer 1 injects ENUM_CATEGORY values → correct filter → rows returned.

  opaque_column (3 Qs)
    district table columns a1-a16 have no semantic meaning in their names.
    Layer 1 injects sample values: a3 ENUM_CATEGORY values=[Prague, central Bohemia, ...]
    and a2 STRING samples=['Hl.m. Praha', 'Benesov', ...].
    At baseline: Haiku cannot distinguish a2 (district name) from a3 (region).

  current_state (3 Qs)
    trans.balance is a running total — each row is the balance AFTER that event.
    "Current balance" = most recent row per account, not AVG or MAX.
    Layer 1 annotates: balance -- process_role=STATE_VARIABLE and provides:
      latest_record_only: {partition_by: ['account_id'], order_by: 'date'}
    At baseline: Haiku computes AVG(balance) or checks any row — semantically wrong.

  distributional (3 Qs)
    Layer 1 computes per-column value_axis extremes (p10/p90 statistical cutoffs)
    and conditional_value_distribution (p50/p90 per ENUM group).
    Examples injected:
      trans.amount -- extremes={'small': '<1320', 'large': '>21200'}
      trans.amount -- dist_by_type: VYDAJ p90=7155, PRIJEM p90=32600
    At baseline: Haiku picks arbitrary round thresholds with no statistical basis.
    With Layer 1: uses the actual data-derived cutoffs.

  quantitative_misinterpretation (3 Qs)
    Requires correct ENUM codes to isolate the right population, combined with
    arithmetic (SUM/ratio) that Layer 1's safe_aggregation flags support.
    At baseline: wrong ENUM codes → 0 rows → cannot compute net credit or ratio.

  time_grain (2 Qs)
    Layer 1 injects time_grains=['monthly'] for date columns and emits an
    AGGREGATE_OVER_TIME operator. Combined with ENUM codes for debit/credit
    filtering, these 2 questions test ENUM + temporal aggregation together.
    At baseline: wrong type code AND potentially wrong time bucket.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -e lib/ anthropic

    # baseline vs layer1, with LLM judge (recommended)
    python3 examples/benchmarks/enrichment_benchmark.py --judge

    # also run layer2 (LLM-augmented enrichment, more API calls)
    python3 examples/benchmarks/enrichment_benchmark.py --judge --layer2

    # save full results
    python3 examples/benchmarks/enrichment_benchmark.py --judge --out results/run.json
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

SQL_FILE     = Path(__file__).parent.parent.parent / "data" / "finance_sqlite.sql"
QUERIES_FILE = Path(__file__).parent.parent.parent / "data" / "finance_benchmark_queries.json"
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

def make_chat_fn(api_key: str, model: str, temperature: float | None = None):
    """Returns (system, prompt) -> str for SQL generation and judging.

    Pass temperature=0 for reproducible SQL generation.
    Omit (None) for models that don't accept temperature (e.g. claude-opus-4-8).
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def call(system: str, prompt: str) -> str:
        kwargs: dict = {"model": model, "max_tokens": 1024, "system": system,
                        "messages": [{"role": "user", "content": prompt}]}
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = client.messages.create(**kwargs)
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
            model=model, max_tokens=1024, temperature=0,
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
        return {"verdict": "error", "reason": f"no JSON in response: {raw[:120]}"}
    except Exception as e:
        return {"verdict": "error", "reason": str(e)[:120]}


# ── Benchmark run ──────────────────────────────────────────────────────────

def run(use_judge: bool, use_layer2: bool, model: str, judge_model: str,
        out_path: str | None, report_path: str | None = None) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set ANTHROPIC_API_KEY first.")
        return

    chat       = make_chat_fn(api_key, model, temperature=0)   # deterministic SQL generation
    judge_chat = make_chat_fn(api_key, judge_model)             # no temperature — opus-4-8 doesn't accept it
    queries = json.loads(QUERIES_FILE.read_text())
    cats    = sorted({q["category"] for q in queries})
    n       = len(queries)

    print()
    print(DIV)
    print(f"Finance NL2SQL enrichment benchmark   model={model}")
    if use_judge:
        print(f"Judge model: {judge_model}")
    print(f"Questions: {n}   judge: {'yes' if use_judge else 'no'}   enriched+L2: {'yes' if use_layer2 else 'no'}")
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
        ("enriched", layer1_ctx),
    ]

    if use_layer2:
        print("Step 2 — LLM-augmented enrichment (Layer 2) …")
        r2         = build_registry(tmp, llm_fn=make_enrich_fn(api_key, model))
        layer2_ctx = build_layer1_context(r2)
        conditions.append(("enriched+L2", layer2_ctx))

    cnames = [c for c, _ in conditions]
    print(f"\nContext sizes:")
    for cname, ctx in conditions:
        print(f"  {cname:<10} {len(ctx):>6} chars")

    # ── Run questions ──────────────────────────────────────────────────────
    print(f"\nRunning {n} questions × {len(conditions)} conditions …")
    print(f"  SQL execution  : OK = ran + returned rows | exec = ran + empty | FAIL = error")
    if use_judge:
        print(f"  Semantic judge : correct | partial | incorrect  (evaluated by {judge_model})")
    print()
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
                verdict_obj = judge(judge_chat, q["intent"], q["expected_behavior"],
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

        exec_parts = "  ".join(
            f"{cn}={'OK' if row[cn]['has_rows'] else ('exec(0 rows)' if row[cn]['exec_ok'] else 'FAIL(error)')}"
            for cn in cnames
        )
        print(f"    SQL exec   : {exec_parts}")
        if use_judge:
            judge_parts = "  ".join(
                f"{cn}={(row[cn]['judge'] or {}).get('verdict','?')}"
                for cn in cnames
            )
            print(f"    semantics  : {judge_parts}")
            # surface any judge errors so failures are visible
            for cn in cnames:
                j = row[cn].get("judge") or {}
                if j.get("verdict") == "error":
                    print(f"    judge-error ({cn}): {j.get('reason', '?')}")
        print()
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
    print()
    print("── SQLite execution (mechanical: did the SQL run and return rows?) ──")
    header = f"{'Metric':<35}" + "".join(f"{c:>{col_w}}" for c in cnames)
    print(header)
    print(DIV2)

    for label, key in [
        ("SQL runs without error",       "exec_ok"),
        ("SQL returns non-empty result", "has_rows"),
    ]:
        row_vals = {c: sum(1 for r in results if r[c][key]) for c in cnames}
        line = f"{label:<35}"
        for c in cnames:
            line += f"{row_vals[c]:>{col_w-3}}/{n}  "
        print(line)

    if use_judge:
        print()
        print(f"── Semantic correctness (LLM judge: {judge_model}) ──")
        header2 = f"{'Metric':<35}" + "".join(f"{c:>{col_w}}" for c in cnames)
        print(header2)
        print(DIV2)
        for verdict, label in [("correct", "Correct (fully answers question)"),
                                ("partial", "Partial (right direction, wrong detail)"),
                                ("incorrect", "Incorrect (wrong semantics)")]:
            row_vals = {c: sum(1 for r in results
                               if (r[c]["judge"] or {}).get("verdict") == verdict)
                        for c in cnames}
            line = f"{label:<35}"
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

    # By category — execution (has_rows) and semantic correctness side by side
    print(f"\n── By category ──")
    print(f"  {'Category':<32}" + "".join(f"  {c[:8]:<8}" for c in cnames) + "  n")
    print(f"  {'(SQL: % returning rows)':<32}" + "".join(f"  {'exec%':>8}" for _ in cnames))
    print(DIV2)
    for cat in cats:
        cat_r = [r for r in results if r["category"] == cat]
        nc    = len(cat_r)
        line  = f"  {cat:<32}"
        for c in cnames:
            ok   = sum(1 for r in cat_r if r[c]["has_rows"])
            line += f"  {pct(ok, nc):>8}"
        print(line + f"  {nc}")

    if use_judge:
        print(f"\n  {'Category':<32}" + "".join(f"  {c[:8]:<8}" for c in cnames) + "  n")
        print(f"  {'(Semantic: % fully correct)':<32}" + "".join(f"  {'correct':>8}" for _ in cnames))
        print(DIV2)
        for cat in cats:
            cat_r = [r for r in results if r["category"] == cat]
            nc    = len(cat_r)
            line  = f"  {cat:<32}"
            for c in cnames:
                ok = sum(1 for r in cat_r if (r[c]["judge"] or {}).get("verdict") == "correct")
                line += f"  {pct(ok, nc):>8}"
            print(line + f"  {nc}")

    # Per-question detail
    print(f"\n{'Per-question detail'}")
    if use_judge:
        print(f"  Columns show: SQL-exec(rows?|error?) / semantic-verdict")
        print(f"  SQL-exec : OK=ran+rows  exec=ran+empty  FAIL=error")
        print(f"  Semantic : cor=correct  par=partial  inc=incorrect  (judge: {judge_model})")
    print(DIV2)
    hdr = f"  {'id':<14} {'category':<24}"
    for c in cnames:
        hdr += f" {c:<10}"
    hdr += "  changes"
    print(hdr)
    print(f"  {'-'*14} {'-'*24}" + "".join(f" {'-'*10}" for _ in cnames) + "  " + "-"*30)

    for r in results:
        line   = f"  {r['id']:<14} {r['category']:<24}"
        status = {}
        for c in cnames:
            s = "OK" if r[c]["has_rows"] else ("exec" if r[c]["exec_ok"] else "FAIL")
            if use_judge:
                v = (r[c]["judge"] or {}).get("verdict", "?")
                s = f"{s}/{v[:3]}"
            status[c] = s
            line += f" {s:<10}"

        changes = []
        if "enriched" in cnames and not r["baseline"]["has_rows"] and r["enriched"]["has_rows"]:
            changes.append("enrichment fixed")
        if "enriched+L2" in cnames and not r["enriched"]["has_rows"] and r["enriched+L2"]["has_rows"]:
            changes.append("L2 fixed")
        if "enriched" in cnames and r["baseline"]["has_rows"] and not r["enriched"]["has_rows"]:
            changes.append("enrichment regressed")
        print(line + "  " + "; ".join(changes))

    # Show one example failure vs fix
    fixed = [r for r in results
             if "enriched" in cnames
             and not r["baseline"]["has_rows"]
             and r["enriched"]["has_rows"]]
    if fixed:
        ex = fixed[0]
        print(f"\n── Example: enrichment fixed '{ex['id']}' ──")
        print(f"  Q: {ex['intent']}")
        print(f"  baseline SQL : {(ex['baseline']['sql'] or '(none)')[:120]}")
        if ex["baseline"]["error"]:
            print(f"  baseline err : {ex['baseline']['error'][:80]}")
        print(f"  enriched SQL : {(ex['enriched']['sql'] or '(none)')[:120]}")
        print(f"  enriched rows: {ex['enriched']['n_rows']}")

    # Report
    if report_path:
        md = generate_report(results, cnames, use_judge, judge_model, model, n,
                             {c: len(ctx) for c, ctx in conditions})
        rpt = Path(report_path)
        rpt.parent.mkdir(parents=True, exist_ok=True)
        rpt.write_text(md)
        print(f"\nMarkdown report saved → {report_path}")

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


# ── Report generator ───────────────────────────────────────────────────────

def generate_report(results: list, cnames: list[str], use_judge: bool,
                    judge_model: str, model: str, n: int,
                    ctx_sizes: dict[str, int]) -> str:
    """Render benchmark results as a GitHub-flavoured markdown report with Mermaid charts."""
    from datetime import datetime as _dt

    cats   = sorted({r["category"] for r in results})
    now    = _dt.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def _pct(num: int, den: int) -> str:
        return f"{num/den:.0%}" if den else "—"

    def _bar(pct_float: float, width: int = 15) -> str:
        filled = round(pct_float * width)
        return "█" * filled + "░" * (width - filled)

    def _verdict_count(cond: str, verdict: str) -> int:
        return sum(1 for r in results if (r[cond]["judge"] or {}).get("verdict") == verdict)

    def _cat_correct(cat: str, cond: str) -> tuple[int, int]:
        cat_r = [r for r in results if r["category"] == cat]
        ok    = sum(1 for r in cat_r if (r[cond]["judge"] or {}).get("verdict") == "correct")
        return ok, len(cat_r)

    def _cat_rows(cat: str, cond: str) -> tuple[int, int]:
        cat_r = [r for r in results if r["category"] == cat]
        ok    = sum(1 for r in cat_r if r[cond]["has_rows"])
        return ok, len(cat_r)

    lines: list[str] = []
    a = lines.append

    # ── Header ──
    a("# NL2SQL Enrichment Benchmark — Results")
    a("")
    a(f"**SQL model:** `{model}` (temperature=0, deterministic) | **Judge:** `{judge_model}`  ")
    a(f"**Questions:** {n} | **Conditions:** {', '.join(f'`{c}`' for c in cnames)} | "
      f"**Context sizes:** {' vs '.join(f'{c}={ctx_sizes[c]:,} chars' for c in cnames)}  ")
    a(f"**Last run:** {now}")
    a("")
    a("> Re-generate: `python3 examples/benchmarks/enrichment_benchmark.py --judge "
      f"--model {model} --report`")
    a("")
    a("---")
    a("")

    # ── Overall summary ──
    a("## Overall results")
    a("")
    exec_ok_b = sum(1 for r in results if r["baseline"]["exec_ok"])
    exec_ok_l = sum(1 for r in results if r["layer1"]["exec_ok"])
    rows_b    = sum(1 for r in results if r["baseline"]["has_rows"])
    rows_l    = sum(1 for r in results if r["layer1"]["has_rows"])

    a("| Metric | baseline | layer1 | Δ |")
    a("|--------|----------|--------|---|")
    a(f"| SQL runs without error | {exec_ok_b}/{n} ({_pct(exec_ok_b,n)}) | "
      f"{exec_ok_l}/{n} ({_pct(exec_ok_l,n)}) | {exec_ok_l-exec_ok_b:+d} |")
    a(f"| SQL returns non-empty result | {rows_b}/{n} ({_pct(rows_b,n)}) | "
      f"{rows_l}/{n} ({_pct(rows_l,n)}) | {rows_l-rows_b:+d} |")

    if use_judge:
        for verdict, label in [
            ("correct",   "Semantically **correct**"),
            ("partial",   "Semantically partial"),
            ("incorrect", "Semantically incorrect"),
        ]:
            b = _verdict_count("baseline", verdict)
            l = _verdict_count("layer1",   verdict)
            a(f"| {label} | {b}/{n} ({_pct(b,n)}) | {l}/{n} ({_pct(l,n)}) | **{l-b:+d}** |")

    a("")

    # ── ASCII progress bars (overall) ──
    if use_judge:
        a("```")
        a(f"Semantic correctness (% of {n} questions judged fully correct)")
        a("")
        for c in cnames:
            ok  = _verdict_count(c, "correct")
            frac = ok / n
            a(f"  {c:<10}  {_bar(frac)}  {_pct(ok, n):>4}  ({ok}/{n})")
        a("```")
        a("")

    a("---")
    a("")

    # ── By-category semantic chart ──
    if use_judge:
        a("## Semantic correctness by category")
        a("")

        # Sort categories: biggest gain first, control last
        def _gain(cat: str) -> float:
            bl, nl = _cat_correct(cat, "baseline")[0], _cat_correct(cat, "layer1")[0]
            nc     = _cat_correct(cat, "baseline")[1]
            return (bl - nl) / nc if nc else 0   # negative = improvement

        sorted_cats = sorted(cats, key=_gain)

        # Mermaid bar chart
        short = {
            "none":                         "none",
            "enum_coded_value":             "enum",
            "opaque_column":                "opaque",
            "current_state":                "state",
            "distributional":               "distrib",
            "quantitative_misinterpretation": "quant",
            "time_grain":                   "time",
        }
        x_labels = [f'"{short.get(c, c[:6])}"' for c in sorted_cats]
        b_vals   = [round(_cat_correct(c, "baseline")[0] / _cat_correct(c, "baseline")[1] * 100)
                    for c in sorted_cats]
        l_vals   = [round(_cat_correct(c, "layer1")[0] / _cat_correct(c, "layer1")[1] * 100)
                    for c in sorted_cats]

        a("```mermaid")
        a("xychart-beta")
        a('    title "Semantic Correctness by Category (%)"')
        a(f"    x-axis [{', '.join(x_labels)}]")
        a('    y-axis "% semantically correct" 0 --> 100')
        a(f"    bar [{', '.join(str(v) for v in b_vals)}]")
        a(f"    bar [{', '.join(str(v) for v in l_vals)}]")
        a("```")
        a("")
        a("*First bar = baseline · Second bar = layer1 — sorted by improvement*")
        a("")

        # Table
        a("| Category | n | Baseline | Layer 1 | Δ |")
        a("|---|---|---|---|---|")
        for cat in sorted_cats:
            b_ok, nc = _cat_correct(cat, "baseline")
            l_ok, _  = _cat_correct(cat, "layer1")
            delta    = l_ok - b_ok
            delta_pp = round((l_ok - b_ok) / nc * 100)
            flag     = " ★" if delta_pp >= 50 else (" ↑" if delta_pp > 0 else "")
            a(f"| {cat} | {nc} | {b_ok}/{nc} ({_pct(b_ok, nc)}) | "
              f"{l_ok}/{nc} ({_pct(l_ok, nc)}) | {delta_pp:+d}pp{flag} |")
        a("")
        a("---")
        a("")

    # ── SQL execution by category ──
    a("## SQL execution by category (% returning non-empty result)")
    a("")

    ex_cats = sorted(cats, key=lambda c: _cat_rows(c, "layer1")[0] - _cat_rows(c, "baseline")[0],
                     reverse=True)
    x_labels2 = [f'"{short.get(c, c[:6])}"' for c in ex_cats]
    b_ex = [round(_cat_rows(c, "baseline")[0] / _cat_rows(c, "baseline")[1] * 100) for c in ex_cats]
    l_ex = [round(_cat_rows(c, "layer1")[0]   / _cat_rows(c, "layer1")[1]   * 100) for c in ex_cats]

    a("```mermaid")
    a("xychart-beta")
    a('    title "SQL Execution: % Questions Returning Rows"')
    a(f"    x-axis [{', '.join(x_labels2)}]")
    a('    y-axis "% returning rows" 0 --> 100')
    a(f"    bar [{', '.join(str(v) for v in b_ex)}]")
    a(f"    bar [{', '.join(str(v) for v in l_ex)}]")
    a("```")
    a("")

    a("| Category | n | Baseline rows | Layer 1 rows | Δ |")
    a("|---|---|---|---|---|")
    for cat in ex_cats:
        b_ok, nc = _cat_rows(cat, "baseline")
        l_ok, _  = _cat_rows(cat, "layer1")
        delta_pp = round((l_ok - b_ok) / nc * 100)
        a(f"| {cat} | {nc} | {b_ok}/{nc} ({_pct(b_ok, nc)}) | "
          f"{l_ok}/{nc} ({_pct(l_ok, nc)}) | {delta_pp:+d}pp |")
    a("")
    a("---")
    a("")

    # ── Per-question table ──
    a("## Per-question results")
    a("")
    if use_judge:
        a("Exec: **OK** = ran + returned rows · **exec** = ran + 0 rows · **FAIL** = SQL error  ")
        a("Semantic: **cor** = correct · **par** = partial · **inc** = incorrect")
    a("")

    # Build header
    hdr  = "| ID | Category | Question"
    sep  = "|---|---|---"
    for c in cnames:
        hdr += f" | {c} exec | {c} semantic"
        sep += " |---|---"
    hdr += " |"
    sep += " |"
    a(hdr)
    a(sep)

    emoji_exec = {"rows": "✅", "empty": "⬜", "error": "❌"}
    emoji_sem  = {"correct": "✅", "partial": "🟡", "incorrect": "❌", "error": "⚠️"}

    for r in results:
        intent_short = r["intent"][:55] + "…" if len(r["intent"]) > 55 else r["intent"]
        row = f"| {r['id']} | {r['category']} | {intent_short}"
        for c in cnames:
            exec_s = "✅ OK" if r[c]["has_rows"] else ("⬜ exec" if r[c]["exec_ok"] else "❌ FAIL")
            if use_judge:
                v     = (r[c]["judge"] or {}).get("verdict", "error")
                sem_s = {"correct": "✅ cor", "partial": "🟡 par",
                         "incorrect": "❌ inc", "error": "⚠️ err"}.get(v, v)
            else:
                sem_s = "—"
            row += f" | {exec_s} | {sem_s}"
        row += " |"
        a(row)

    a("")
    a("---")
    a("")

    # ── Enrichment features covered ──
    a("## What each category tests")
    a("")
    descriptions = {
        "none":
            "**Control.** Questions answerable from column names alone. Both conditions "
            "expected correct. Validates that the benchmark is not giving unfair advantage.",
        "enum_coded_value":
            "**ENUM code injection.** Columns store Czech domain codes (`VKLAD`, `POJISTNE`, "
            "`SIPO`, `PREVOD NA UCET`…) that an LLM cannot infer from English intent. "
            "Layer 1 injects `ENUM_CATEGORY` values into the context. Baseline generates "
            "English words as filter values → 0 rows. Layer 1 uses the actual codes → rows returned.",
        "opaque_column":
            "**Opaque column disambiguation.** `district` columns `a2`–`a16` have no "
            "meaningful names. Layer 1 injects `a3` as `ENUM_CATEGORY` with region values "
            "(`Prague`, `central Bohemia`…) and `a2` as STRING with district name samples. "
            "Baseline confuses the two columns.",
        "current_state":
            "**Process semantics / STATE_VARIABLE.** `trans.balance` is a running total — "
            "each row is the account balance *after* that event. 'Current balance' requires "
            "the most recent row per account, not AVG or MAX. Layer 1 annotates `balance` "
            "as `STATE_VARIABLE` and provides `latest_record_only: partition_by=[account_id]`.",
        "distributional":
            "**Statistical extremes.** Layer 1 computes `value_axis` extreme regions from the "
            "actual data distribution: `trans.amount` large = > 21 200, "
            "`trans.balance` small = < 9 500. Baseline picks arbitrary round-number thresholds.",
        "quantitative_misinterpretation":
            "**Ratio and net-credit queries.** Requires correctly isolating debit "
            "(`type='VYDAJ'`) vs credit (`type='PRIJEM'`) transactions. Baseline uses "
            "English words → 0 rows for both populations → formula cannot be computed.",
        "time_grain":
            "**Temporal bucketing + ENUM.** Monthly aggregations filtered by transaction type "
            "(`type='PRIJEM'`). Layer 1 provides `time_grains=['monthly']` and an "
            "`AGGREGATE_OVER_TIME` operator. Baseline fails on both: wrong ENUM code "
            "and potentially wrong time bucket.",
    }
    for cat in sorted(cats):
        a(f"### {cat}")
        a("")
        a(descriptions.get(cat, ""))
        a("")

    return "\n".join(lines)


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Finance NL2SQL enrichment benchmark")
    p.add_argument("--judge",   action="store_true",
                   help="LLM-as-judge for semantic correctness (+2 pts per question)")
    p.add_argument("--layer2",  action="store_true",
                   help="Also run LLM-augmented enrichment (Layer 2) as a third condition")
    p.add_argument("--model",        default=os.environ.get("BLUE_DATA_LLM_MODEL", "claude-opus-4-8"),
                   help="Model for SQL generation (default: claude-opus-4-8)")
    p.add_argument("--judge-model",  default=None,
                   help="Separate model for judging semantic correctness. Defaults to claude-sonnet-4-6. "
                        "Use a stronger model than the SQL generator. Note: claude-opus-4-8 requires extended "
                        "thinking and will fail here — use claude-sonnet-4-6 or claude-haiku-4-5-20251001.")
    p.add_argument("--out",          default=None, help="Save detailed JSON results to this path")
    p.add_argument("--report",       default=None, const="examples/benchmarks/RESULTS.md",
                   nargs="?",
                   help="Write markdown report with charts (default path: examples/benchmarks/RESULTS.md)")
    args = p.parse_args()
    judge_model = args.judge_model or "claude-sonnet-4-6"
    run(use_judge=args.judge, use_layer2=args.layer2, model=args.model,
        judge_model=judge_model, out_path=args.out, report_path=args.report)


if __name__ == "__main__":
    main()
