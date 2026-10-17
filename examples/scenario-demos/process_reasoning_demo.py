"""
Demo 4 — Process Reasoning
============================
Problem : LLMs treat event-log tables as static snapshots.
          "Current balance" → AVG(balance).  Wrong.
          "Monthly trend"   → flat COUNT(*).  Wrong.
          "Repeated overdraft" → WHERE balance < 0.  Ignores sequence.
Solution: blue-data Layer 1 detects EVENT tables, identifies event_time,
          state variables, and process operators — zero LLM cost.
          The enriched schema context guides the SQL model to temporally
          correct queries.

Usage:
    # Run demo (zero API key — shows Layer 1 detection + pre-built SQL examples)
    python3 examples/process_reasoning_demo.py

    # Live mode: regenerate SQL examples in real-time
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/process_reasoning_demo.py --live
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SQL_FILE = Path(__file__).parent.parent.parent / "data" / "finance_sqlite.sql"
DATABASE = "finance"
DIV      = "=" * 68
DIV2     = "-" * 68

# Pre-built examples showing baseline vs process-aware SQL for each question.
# Each entry shows the failure mode and the correct temporal approach.
EXAMPLES = [
    {
        "id":       "p1",
        "question": "What is the current account balance for each account?",
        "why":      "balance is a running STATE — must use the most recent row, not AVG or SUM",
        "baseline": """\
SELECT account_id, AVG(balance) AS current_balance
FROM trans
GROUP BY account_id""",
        "baseline_problem": "AVG(balance) averages all historical snapshots — semantically wrong",
        "enriched": """\
SELECT account_id, balance AS current_balance
FROM trans
WHERE (account_id, date) IN (
    SELECT account_id, MAX(date) FROM trans GROUP BY account_id
)""",
        "enriched_fix": "row_semantics=EVENT + event_time=date → balance at most recent event = current state",
    },
    {
        "id":       "p2",
        "question": "Show monthly transaction count for account 2 between 1993 and 1997",
        "why":      "trans is an EVENT log — needs GROUP BY on event_time, not a flat count",
        "baseline": """\
SELECT COUNT(*) AS transaction_count
FROM trans
WHERE account_id = 2
  AND date BETWEEN '1993-01-01' AND '1997-12-31'""",
        "baseline_problem": "Returns a single number — loses all temporal structure",
        "enriched": """\
SELECT strftime('%Y-%m', date) AS month,
       COUNT(*)                AS transaction_count
FROM trans
WHERE account_id = 2
  AND date BETWEEN '1993-01-01' AND '1997-12-31'
GROUP BY month
ORDER BY month""",
        "enriched_fix": "event_time=date + time_grains=[monthly] → GROUP BY strftime month",
    },
    {
        "id":       "p3",
        "question": "Which accounts had a negative balance more than once?",
        "why":      "needs COUNT of occurrences across ordered events, not a single row check",
        "baseline": """\
SELECT DISTINCT account_id
FROM trans
WHERE balance < 0""",
        "baseline_problem": "EXISTS check — returns any account with even one negative row",
        "enriched": """\
SELECT account_id, COUNT(*) AS negative_balance_events
FROM trans
WHERE balance < 0
GROUP BY account_id
HAVING COUNT(*) > 1
ORDER BY negative_balance_events DESC""",
        "enriched_fix": "row_semantics=EVENT + requires_temporal_reasoning → count events, not existence",
    },
    {
        "id":       "p4",
        "question": "Show the sequence of balance changes for account 1",
        "why":      "balance is a running state — must be read in chronological order",
        "baseline": """\
SELECT date, balance
FROM trans
WHERE account_id = 1""",
        "baseline_problem": "No ORDER BY — rows returned in arbitrary storage order",
        "enriched": """\
SELECT date,
       amount,
       type,
       balance
FROM trans
WHERE account_id = 1
ORDER BY date ASC""",
        "enriched_fix": "event_time=date → ORDER BY date to reconstruct state sequence",
    },
]

SYSTEM_PROMPT = """\
You are an expert SQL assistant. Convert the natural language question into
a correct, executable SQLite query.
- Output ONLY a single SQL query inside a ```sql code block.
- Use table and column names exactly as in the schema.
- SQLite: strftime('%Y-%m', date_col) for month grouping.
- For "current" or "latest" values use the most recent row by date, not AVG.
"""


# ── Infrastructure ─────────────────────────────────────────────────────────

def build_db(tmp_dir: str) -> str:
    db_path = os.path.join(tmp_dir, f"{DATABASE}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SQL_FILE.read_text())
    conn.close()
    return db_path


def build_registry(db_dir: str) -> DataRegistry:
    source = SQLiteDBSource(
        name=DATABASE,
        properties={"connection": {"database_directory": db_dir}},
    )
    reg = DataRegistry(store=MemoryJSONSource(), metadata_enricher=MetaData(llm_fn=None))
    reg.register_source(source)
    reg.sync_all(recursive=True)
    reg.collect_source_stats(DATABASE, recursive=True)
    reg.enrich_source_metadata(DATABASE, recursive=True, rebuild=False)
    return reg


def make_chat_fn(api_key: str, model: str):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def call(system: str, prompt: str) -> str:
        resp = client.messages.create(
            model=model, max_tokens=512, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        for b in resp.content:
            if b.type == "text":
                return b.text
        return ""
    return call


def extract_sql(text: str) -> str | None:
    m = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def run_sql(db_path: str, sql: str) -> tuple[list, str | None]:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return [], str(e)


def _result_signature(rows: list) -> list:
    """Order-insensitive, column-name-insensitive signature of a result set, so
    a query that returns the right data counts as correct regardless of column
    aliases or row order."""
    return sorted(tuple(sorted(str(v) for v in row.values())) for row in rows)


def _matches_reference(rows: list, err: str | None, ref_rows: list) -> bool:
    """A generated query is correct only if it executed without error and
    returned the same data as the reference query. Missing SQL and execution
    errors (``err`` set) count as failures, never as correct."""
    if err or rows is None:
        return False
    return _result_signature(rows) == _result_signature(ref_rows)


# ── Context builders ───────────────────────────────────────────────────────

def _vsi(reg, name):
    return reg.get_source_database_collection_entity_attribute_property(
        DATABASE, DATABASE, "public", "trans", name, "value_semantics"
    ) or {}


def _samples(reg, attr):
    vsi = _vsi(reg, attr["name"])
    return (vsi.get("examples") or
            attr.get("properties", {}).get("stats", {}).get("sample_values", []))


def build_baseline_ddl(reg: DataRegistry) -> str:
    attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", "trans")
    lines = ["-- Schema (raw, no enrichment)", "", "CREATE TABLE trans ("]
    lines.append(",\n".join(f"    {a['name']}" for a in attrs))
    lines.append(");\n")
    return "\n".join(lines)


def build_process_enriched_ddl(reg: DataRegistry) -> str:
    attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", "trans")
    lines = ["-- Schema with blue-data Layer 1 process enrichment", "", "CREATE TABLE trans ("]
    col_lines = []
    for attr in attrs:
        name = attr["name"]
        vsi  = _vsi(reg, name)
        st   = vsi.get("semantic_type", "")
        annots = []
        if st:
            annots.append(f"type={st}")
        if st == "ENUM_CATEGORY" or vsi.get("is_categorical"):
            samples = _samples(reg, attr)
            if samples:
                distinct = list(dict.fromkeys(str(v) for v in samples))
                annots.append(f"values=[{', '.join(distinct)}]")
        pvr = reg.get_source_database_collection_entity_attribute_property(
            DATABASE, DATABASE, "public", "trans", name, "process_vst_role"
        ) or {}
        if pvr.get("process_vst_role"):
            annots.append(f"process_role={pvr['process_vst_role']}")
        tgc = reg.get_source_database_collection_entity_attribute_property(
            DATABASE, DATABASE, "public", "trans", name, "time_grain_candidates"
        )
        if tgc:
            annots.append(f"time_grains={tgc}")
        col_lines.append(f"    {name}" + ("  -- " + " | ".join(annots) if annots else ""))
    lines.append(",\n".join(col_lines))
    lines.append(");\n")

    ps = reg.get_source_database_collection_entity_property(
        DATABASE, DATABASE, "public", "trans", "process_semantics"
    )
    if ps:
        lines.append(f"-- [process]  row_semantics={ps.get('row_semantics')}  "
                     f"event_time={ps.get('event_time')}")
        c = ps.get("constraints", {})
        flags = [k for k in ("requires_temporal_reasoning",
                              "row_local_substitution_invalid") if c.get(k)]
        if flags:
            lines.append(f"-- [constraint]  {', '.join(flags)}")
    ops = reg.get_source_database_collection_entity_property(
        DATABASE, DATABASE, "public", "trans", "process_operators"
    ) or []
    for op in ops:
        lines.append(f"-- [operator]  {op['operator']}")
    return "\n".join(lines)


# ── Display ────────────────────────────────────────────────────────────────

def show_detection(reg: DataRegistry) -> None:
    ps = reg.get_source_database_collection_entity_property(
        DATABASE, DATABASE, "public", "trans", "process_semantics"
    )
    ops = reg.get_source_database_collection_entity_property(
        DATABASE, DATABASE, "public", "trans", "process_operators"
    ) or []
    print()
    if ps:
        print("  trans table auto-detected:")
        print(f"    row_semantics  = {ps.get('row_semantics')}")
        print(f"    event_time     = {ps.get('event_time')}")
        c = ps.get("constraints", {})
        flags = [k for k in ("requires_temporal_reasoning",
                              "row_local_substitution_invalid") if c.get(k)]
        if flags:
            print(f"    constraints    = {', '.join(flags)}")
    if ops:
        print(f"    operators      = {[op['operator'] for op in ops]}")
    print()
    print("  Column process roles:")
    for col in ["date", "balance", "amount", "account_id"]:
        pvr = reg.get_source_database_collection_entity_attribute_property(
            DATABASE, DATABASE, "public", "trans", col, "process_vst_role"
        ) or {}
        role = pvr.get("process_vst_role")
        if role:
            print(f"    trans.{col:<14}  process_role = {role}")
    print()
    print("  No human annotation. No LLM.")


def _print_sql(label: str, sql: str, indent: str = "    ") -> None:
    lines = sql.strip().splitlines()
    print(f"  {label}")
    for line in lines:
        print(f"{indent}{line}")


def show_example(ex: dict, b_sql=None, e_sql=None, b_rows=None, e_rows=None,
                 b_err=None, e_err=None, b_ok=None, e_ok=None, live=False) -> None:
    print()
    print(f"  [{ex['id']}]  {ex['question']}")
    print(f"         Why hard: {ex['why']}")
    print()

    bsql = b_sql or ex["baseline"]
    esql = e_sql or ex["enriched"]

    if live and b_rows is not None:
        b_result = f"error: {b_err}" if b_err else f"{len(b_rows)} rows"
        e_result = f"error: {e_err}" if e_err else f"{len(e_rows)} rows"
        b_mark = "✓ matches reference" if b_ok else "✗ does not match reference"
        e_mark = "✓ matches reference" if e_ok else "✗ does not match reference"
        _print_sql("baseline (no enrichment):", bsql)
        print(f"  → {b_result}  {b_mark}  ({ex['baseline_problem']})")
        print()
        _print_sql("enriched (Layer 1):", esql)
        print(f"  → {e_result}  {e_mark}  ({ex['enriched_fix']})")
    else:
        _print_sql("baseline (no enrichment):", bsql)
        print(f"  ✗ {ex['baseline_problem']}")
        print()
        _print_sql("enriched (Layer 1):", esql)
        print(f"  ✓ {ex['enriched_fix']}")


# ── Main ───────────────────────────────────────────────────────────────────

def run(live: bool, model: str) -> None:
    print()
    print(DIV)
    print("Demo 4 — Process Reasoning")
    print(DIV)
    print()
    print("  Problem : LLMs treat event-log tables as static snapshots.")
    print("            'Current balance' → AVG(balance).  Wrong.")
    print("            'Monthly trend'   → flat COUNT(*). Wrong.")
    print("  Solution: blue-data Layer 1 detects EVENT tables, event_time,")
    print("            and state variables — zero LLM cost.")

    tmp = tempfile.mkdtemp(prefix="process-demo-")
    db  = build_db(tmp)

    print()
    print(DIV2)
    print("Step 1 — Connect database → Layer 1 process detection  (no LLM)")
    print(DIV2)

    reg = build_registry(tmp)
    show_detection(reg)

    baseline_ctx = build_baseline_ddl(reg)
    enriched_ctx = build_process_enriched_ddl(reg)

    print()
    print(DIV2)
    mode_label = f"live SQL generation  (model: {model})" if live else "pre-built examples"
    print(f"Step 2 — Baseline vs process-enriched SQL  [{mode_label}]")
    print(DIV2)

    if live:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("\nERROR: set ANTHROPIC_API_KEY to use --live.")
            return
        chat = make_chat_fn(api_key, model)

    baseline_correct = 0
    enriched_correct = 0

    for ex in EXAMPLES:
        if live:
            b_sql          = extract_sql(chat(SYSTEM_PROMPT,
                f"Schema:\n```\n{baseline_ctx}\n```\n\nQuestion: {ex['question']}\n\nWrite a SQLite query."))
            e_sql          = extract_sql(chat(SYSTEM_PROMPT,
                f"Schema:\n```\n{enriched_ctx}\n```\n\nQuestion: {ex['question']}\n\nWrite a SQLite query."))
            b_rows, b_err  = run_sql(db, b_sql) if b_sql else ([], "no SQL generated")
            e_rows, e_err  = run_sql(db, e_sql) if e_sql else ([], "no SQL generated")
            # Score against the reference answer rather than assuming correctness.
            ref_rows, _    = run_sql(db, ex["enriched"])
            b_ok           = _matches_reference(b_rows, b_err, ref_rows)
            e_ok           = _matches_reference(e_rows, e_err, ref_rows)
            baseline_correct += int(b_ok)
            enriched_correct += int(e_ok)
            show_example(ex, b_sql=b_sql, e_sql=e_sql, b_rows=b_rows, e_rows=e_rows,
                         b_err=b_err, e_err=e_err, b_ok=b_ok, e_ok=e_ok, live=True)
        else:
            show_example(ex)

    print()
    print(DIV)
    print("Result")
    print(DIV)
    print()
    n = len(EXAMPLES)
    if live:
        print(f"  baseline  {baseline_correct}/{n} queries matched the reference answer")
        print(f"  enriched  {enriched_correct}/{n} queries matched the reference answer")
    else:
        print(f"  {n} process reasoning failure modes — all fixed by Layer 1 enrichment")
    print()
    print("  row_semantics=EVENT           → each row is a point-in-time event")
    print("  event_time=date               → ORDER BY / GROUP BY on date")
    print("  requires_temporal_reasoning   → count occurrences, not existence")
    print("  All detected from data — zero annotation, zero LLM cost.")
    print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true",
                   help="Generate SQL in real-time with ANTHROPIC_API_KEY (otherwise uses pre-built examples)")
    p.add_argument("--model", default=os.environ.get("BLUE_DATA_LLM_MODEL", "claude-haiku-4-5-20251001"))
    args = p.parse_args()
    run(live=args.live, model=args.model)


if __name__ == "__main__":
    main()
