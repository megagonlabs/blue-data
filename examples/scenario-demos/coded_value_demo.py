"""
Demo 1 — Coded Value Disambiguation
=====================================
Problem : SQL databases store values as codes — PRIJEM, VYDAJ, UVER, A/B/C/D.
          Baseline LLMs guess English equivalents and get 0 results.
Solution: blue-data Layer 1 auto-detects ENUM_CATEGORY columns and captures
          their actual values from data. Zero LLM cost, zero annotation.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 examples/coded_value_demo.py
"""
from __future__ import annotations

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
TABLES   = ["district", "client", "account", "loan", "trans"]
DIV      = "=" * 68
DIV2     = "-" * 68

SYSTEM_PROMPT = """\
You are an expert SQL assistant. Convert the natural language question into
a correct, executable SQLite query.
- Output ONLY a single SQL query inside a ```sql code block.
- Use table and column names exactly as in the schema.
- Use the exact column values shown in the schema — never substitute English words.
"""

DEMO_QUERIES = [
    {
        "id": "q1",
        "question": "How many credit transactions occurred in 1997?",
        "why":      "baseline guesses type='credit' → 0 rows  |  correct code: PRIJEM",
        "target":   "trans.type",
    },
    {
        "id": "q2",
        "question": "What is the total cash deposit amount per account?",
        "why":      "baseline guesses operation='deposit' → 0 rows  |  correct code: VKLAD",
        "target":   "trans.operation",
    },
    {
        "id": "q3",
        "question": "Find all loans that were completed and fully repaid with no issues",
        "why":      "baseline guesses status='paid' or 'completed' → 0 rows  |  correct code: A",
        "target":   "loan.status",
    },
    {
        "id": "q4",
        "question": "Find accounts with loans currently running with no payment issues",
        "why":      "baseline guesses status='active' or 'running' → 0 rows  |  correct code: C",
        "target":   "loan.status",
    },
    {
        "id": "q5",
        "question": "How many accounts have active loans where the client is in debt?",
        "why":      "baseline guesses status='bad' or 'overdue' → 0 rows  |  correct code: D",
        "target":   "loan.status",
    },
]


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


def run_sql(db_path: str, sql: str) -> tuple[list, str | None]:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return [], str(e)


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
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(SELECT.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def gen_sql(chat, context: str, question: str) -> str | None:
    prompt = f"Schema:\n```\n{context}\n```\n\nQuestion: {question}\n\nWrite a SQLite query."
    return extract_sql(chat(SYSTEM_PROMPT, prompt))


# ── Context builders ───────────────────────────────────────────────────────

def _vsi(reg, table, name):
    return reg.get_source_database_collection_entity_attribute_property(
        DATABASE, DATABASE, "public", table, name, "value_semantics"
    ) or {}


def _samples(reg, table, attr):
    vsi = _vsi(reg, table, attr["name"])
    return (vsi.get("examples") or
            attr.get("properties", {}).get("stats", {}).get("sample_values", []))


def build_baseline_ddl(reg: DataRegistry) -> str:
    """Raw DDL — column names only, no values, no enrichment."""
    lines = ["-- Schema (raw, no enrichment)", ""]
    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        lines.append(f"CREATE TABLE {table} (")
        lines.append(",\n".join(f"    {a['name']}" for a in attrs))
        lines.append(");\n")
    return "\n".join(lines)


def build_enriched_ddl(reg: DataRegistry) -> str:
    """DDL with ENUM values inline — the only signal needed for coded-value queries."""
    lines = ["-- Schema with blue-data Layer 1 enrichment", ""]
    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        lines.append(f"CREATE TABLE {table} (")
        col_lines = []
        for attr in attrs:
            name = attr["name"]
            vsi  = _vsi(reg, table, name)
            st   = vsi.get("semantic_type", "")
            line = f"    {name}"
            if st == "ENUM_CATEGORY" or vsi.get("is_categorical"):
                samples = _samples(reg, table, attr)
                if samples:
                    distinct = list(dict.fromkeys(str(v) for v in samples))
                    vals = ", ".join(distinct)
                    line += f"  -- ENUM: [{vals}]"
            elif st:
                line += f"  -- {st}"
            col_lines.append(line)
        lines.append(",\n".join(col_lines))
        lines.append(");\n")
    return "\n".join(lines)


# ── Display helpers ────────────────────────────────────────────────────────

def _format_sql(sql: str | None, width: int = 80) -> str:
    if not sql:
        return "(no SQL generated)"
    flat = " ".join(sql.split())
    return flat[:width] + "…" if len(flat) > width else flat


def _is_hit(rows: list, err: str | None) -> bool:
    """A successful execution is not a correct answer. A COUNT/SUM over the
    wrong code still returns one row holding 0 (or NULL), so count a single
    scalar aggregate as a hit only when it is a non-zero value."""
    if err or not rows:
        return False
    if len(rows) == 1 and len(rows[0]) == 1:
        (value,) = rows[0].values()
        if value is None:
            return False
        if isinstance(value, (int, float)) and value == 0:
            return False
    return True


def _format_result(rows: list, err: str | None, hit: bool) -> tuple[str, str]:
    if err:
        return f"error: {err[:50]}", "✗"
    if not rows:
        return "0 rows", "✗"
    # Show count and first row snippet
    snippet = str(rows[0])[:60]
    n = len(rows)
    return f"{n} row{'s' if n != 1 else ''}  {snippet}", "✓" if hit else "✗"


# ── Main ───────────────────────────────────────────────────────────────────

def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set ANTHROPIC_API_KEY first.")
        return

    model = os.environ.get("BLUE_DATA_LLM_MODEL", "claude-haiku-4-5-20251001")

    print()
    print(DIV)
    print("Demo 1 — Coded Value Disambiguation")
    print(DIV)
    print()
    print("  Problem : Czech banking database stores values as codes.")
    print("            Baseline LLM guesses English values → 0 results.")
    print("  Solution: blue-data Layer 1 detects ENUM columns and")
    print("            captures actual coded values — zero LLM cost.")

    tmp = tempfile.mkdtemp(prefix="coded-value-demo-")
    db  = build_db(tmp)
    chat = make_chat_fn(api_key, model)

    # ── Step 1: Layer 1 enrichment ─────────────────────────────────────────
    print()
    print(DIV2)
    print("Step 1 — Connect database → Layer 1 enrichment  (no LLM)")
    print(DIV2)
    reg = build_registry(tmp)

    print()
    print("  ENUM columns auto-detected:\n")
    enum_cols = []
    for table in TABLES:
        attrs = reg.list_entity_attributes(DATABASE, DATABASE, "public", table)
        for attr in attrs:
            name = attr["name"]
            vsi  = _vsi(reg, table, name)
            if vsi.get("semantic_type") == "ENUM_CATEGORY" or vsi.get("is_categorical"):
                samples = _samples(reg, table, attr)
                if samples:
                    distinct = list(dict.fromkeys(str(v) for v in samples))
                    vals = ", ".join(distinct)
                    print(f"    {table}.{name:<18}  [{vals}]")
                    enum_cols.append((table, name))

    print()
    print("  No human annotation. No LLM. Deterministic pattern detection.")

    baseline_ctx = build_baseline_ddl(reg)
    enriched_ctx = build_enriched_ddl(reg)

    # ── Step 2: NL2SQL side by side ───────────────────────────────────────
    print()
    print(DIV2)
    print(f"Step 2 — NL2SQL: baseline vs enriched   (SQL model: {model})")
    print(DIV2)

    n = len(DEMO_QUERIES)
    baseline_ok = 0
    enriched_ok = 0

    for q in DEMO_QUERIES:
        print()
        print(f"  [{q['id']}]  {q['question']}")
        print(f"         Target: {q['target']}  |  {q['why']}")
        print()

        b_sql          = gen_sql(chat, baseline_ctx, q["question"])
        b_rows, b_err  = run_sql(db, b_sql) if b_sql else ([], "no SQL generated")
        b_hit          = _is_hit(b_rows, b_err)
        b_res, b_mark  = _format_result(b_rows, b_err, b_hit)
        if b_hit:
            baseline_ok += 1

        e_sql          = gen_sql(chat, enriched_ctx, q["question"])
        e_rows, e_err  = run_sql(db, e_sql) if e_sql else ([], "no SQL generated")
        e_hit          = _is_hit(e_rows, e_err)
        e_res, e_mark  = _format_result(e_rows, e_err, e_hit)
        if e_hit:
            enriched_ok += 1

        print(f"  baseline  {_format_sql(b_sql)}")
        print(f"            → {b_res} {b_mark}")
        print()
        print(f"  enriched  {_format_sql(e_sql)}")
        print(f"            → {e_res} {e_mark}")

        if not b_hit and e_hit:
            print()
            print(f"  ✓ enrichment fixed this query")

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print(DIV)
    print("Result")
    print(DIV)
    print()
    print(f"  baseline  {baseline_ok}/{n}  (guessed English values, missed coded columns)")
    print(f"  enriched  {enriched_ok}/{n}  (used actual ENUM values from data)")
    print()
    print(f"  Layer 1 only — zero LLM enrichment cost.")
    print(f"  Works on any SQL database you connect.")
    print()


if __name__ == "__main__":
    run()
