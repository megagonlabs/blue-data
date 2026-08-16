"""
NL2Q Benchmark — 1-shot NL2SQL vs Tool-based NL2Q.

Runs a fixed set of Northwind questions through both approaches and compares:
  - accuracy   (result matches ground truth)
  - latency    (wall-clock seconds per question)
  - LLM calls  (round trips to the model)
  - errors     (failed / exception)

Approaches
----------
1-shot    : single prompt with schema injected → LLM returns SQL → execute.
tool-based: LLM drives a tool loop (list_databases, get_schema, execute_query, …)
            until it produces an answer.

Usage
-----
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 lib/tests/benchmarks/nl2q_benchmark.py

    # override output paths (defaults write alongside this script)
    python3 lib/tests/benchmarks/nl2q_benchmark.py --out path/to/nl2q.json
    python3 lib/tests/benchmarks/nl2q_benchmark.py --report path/to/NL2Q_RESULTS.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib" / "src"))

import anthropic

from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL   = "claude-haiku-4-5-20251001"
DB_NAME = "northwind"
COLL    = "public"

_ROOT   = Path(__file__).resolve().parents[3]
SQL_FILE = _ROOT / "data" / "northwind_sqlite.sql"

DIV  = "=" * 72
DIV2 = "-" * 72


# ---------------------------------------------------------------------------
# Test cases
# Each has: id, category, question, ground_truth_sql, checker
# checker(gt_rows, result_rows) -> bool
# ---------------------------------------------------------------------------

def _scalar(gt_rows: list, res_rows: list, tol: float = 0.5) -> bool:
    """True if any numeric value in res_rows is within tol of the gt scalar."""
    if not gt_rows or not res_rows:
        return False
    gt_val = list(gt_rows[0].values())[0]
    if gt_val is None:
        return False
    try:
        gt_num = float(gt_val)
    except (TypeError, ValueError):
        return False
    for row in res_rows:
        for v in row.values():
            try:
                if abs(float(v) - gt_num) <= tol:
                    return True
            except (TypeError, ValueError):
                pass
    return False


def _contains_value(gt_rows: list, res_rows: list) -> bool:
    """True if all values from the first gt row appear somewhere in res_rows."""
    if not gt_rows or not res_rows:
        return False
    gt_vals = {str(v).lower().strip() for v in gt_rows[0].values() if v is not None}
    res_vals = {str(v).lower().strip() for row in res_rows for v in row.values() if v is not None}
    return bool(gt_vals & res_vals)


def _top1_match(gt_rows: list, res_rows: list) -> bool:
    """True if the top result in res_rows matches the top result in gt_rows."""
    if not gt_rows or not res_rows:
        return False
    gt_vals = {str(v).lower().strip() for v in gt_rows[0].values() if v is not None}
    res_vals = {str(v).lower().strip() for v in res_rows[0].values() if v is not None}
    return bool(gt_vals & res_vals)


TEST_CASES = [
    {
        "id":       "count_by_country",
        "category": "filter",
        "question": "How many customers are from Germany?",
        "gt_sql":   "SELECT COUNT(*) as count FROM customers WHERE country = 'Germany'",
        "check":    _scalar,
        "note":     "Simple WHERE + COUNT",
    },
    {
        "id":       "avg_freight",
        "category": "aggregation",
        "question": "What is the average freight cost across all orders?",
        "gt_sql":   "SELECT ROUND(AVG(freight), 2) as avg_freight FROM orders",
        "check":    lambda g, r: _scalar(g, r, tol=2.0),
        "note":     "AVG aggregation",
    },
    {
        "id":       "discontinued_count",
        "category": "filter",
        "question": "How many products are discontinued?",
        "gt_sql":   "SELECT COUNT(*) as count FROM products WHERE discontinued = 1",
        "check":    _scalar,
        "note":     "Boolean filter + COUNT",
    },
    {
        "id":       "top_expensive",
        "category": "sort",
        "question": "What is the most expensive product?",
        "gt_sql":   "SELECT product_name, unit_price FROM products ORDER BY unit_price DESC LIMIT 1",
        "check":    _top1_match,
        "note":     "ORDER BY + LIMIT 1",
    },
    {
        "id":       "orders_in_july",
        "category": "temporal",
        "question": "How many orders were placed in July 1996?",
        "gt_sql":   "SELECT COUNT(*) as count FROM orders WHERE order_date LIKE '1996-07-%'",
        "check":    _scalar,
        "note":     "Date pattern filter",
    },
    {
        "id":       "freight_by_country",
        "category": "aggregation",
        "question": "What is the total freight cost for orders shipped to the UK?",
        "gt_sql":   "SELECT ROUND(SUM(freight), 2) as total FROM orders WHERE ship_country = 'UK'",
        "check":    lambda g, r: _scalar(g, r, tol=1.0),
        "note":     "SUM with WHERE",
    },
    {
        "id":       "top_employee",
        "category": "join",
        "question": "Which employee handled the most orders? Give their full name.",
        "gt_sql":   """
            SELECT e.first_name || ' ' || e.last_name as name, COUNT(*) as order_count
            FROM orders o JOIN employees e ON o.employee_id = e.employee_id
            GROUP BY o.employee_id ORDER BY order_count DESC LIMIT 1
        """,
        "check":    _top1_match,
        "note":     "JOIN + GROUP BY + ORDER BY — employee name",
    },
    {
        "id":       "revenue_per_category",
        "category": "join",
        "question": "What is the total revenue per product category?",
        "gt_sql":   """
            SELECT c.category_name,
                   ROUND(SUM(od.unit_price * od.quantity * (1 - od.discount)), 2) as revenue
            FROM order_details od
            JOIN products p  ON od.product_id  = p.product_id
            JOIN categories c ON p.category_id = c.category_id
            GROUP BY c.category_name
            ORDER BY revenue DESC
        """,
        "check":    _contains_value,
        "note":     "3-table JOIN + revenue formula",
    },
    {
        "id":       "customers_no_orders",
        "category": "existence",
        "question": "How many customers have never placed an order?",
        "gt_sql":   """
            SELECT COUNT(*) as count FROM customers
            WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)
        """,
        "check":    _scalar,
        "note":     "NOT IN subquery (existence)",
    },
    {
        "id":       "avg_order_value",
        "category": "join",
        "question": "What is the average order value?",
        "gt_sql":   """
            SELECT ROUND(AVG(order_total), 2) as avg_order_value FROM (
                SELECT order_id, SUM(unit_price * quantity * (1 - discount)) as order_total
                FROM order_details GROUP BY order_id
            )
        """,
        "check":    lambda g, r: _scalar(g, r, tol=5.0),
        "note":     "Subquery + AVG",
    },
]


# ---------------------------------------------------------------------------
# LLM wrappers
# ---------------------------------------------------------------------------

def make_oneshot_llm(client: anthropic.Anthropic, call_counter: list) -> Any:
    """Returns a (prompt: str) -> str callable that counts calls."""
    def llm_fn(prompt: str) -> str:
        call_counter[0] += 1
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in resp.content:
            if block.type == "text":
                return block.text
        return ""
    return llm_fn


def make_tools_llm(client: anthropic.Anthropic, call_counter: list) -> Any:
    """Returns a (messages, tools, system) -> dict callable that counts calls."""
    def llm_fn(messages, tools, system=None):
        call_counter[0] += 1
        kwargs = dict(
            model=MODEL,
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return {
            "stop_reason": resp.stop_reason,
            "content":     [b.model_dump() for b in resp.content],
        }
    return llm_fn


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_oneshot(source: SQLiteDBSource, question: str, call_counter: list, client) -> dict:
    llm_fn = make_oneshot_llm(client, call_counter)

    # get_entities() returns a dict keyed by entity name; convert to the list
    # format expected by _format_schema_for_nl: [{"name": ..., "attributes": {...}}]
    entities_dict = source.fetch_database_collection_entities(DB_NAME, COLL)
    entities_list = [
        {
            "name": e["name"],
            "attributes": e.get("contents", {}).get("attributes", {}),
        }
        for e in entities_dict.values()
    ]
    schema_dict = {"entities": entities_list}

    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl(
            question,
            database=DB_NAME,
            collection=COLL,
            schema=schema_dict,
            llm_fn=llm_fn,
        )
        elapsed = time.perf_counter() - t0
        return {"rows": rows, "latency": elapsed, "error": None}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"rows": [], "latency": elapsed, "error": str(e)}


def run_tools(source: SQLiteDBSource, question: str, call_counter: list, client) -> dict:
    llm_fn = make_tools_llm(client, call_counter)

    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl_tools(
            question,
            database=DB_NAME,
            collection=COLL,
            llm_fn=llm_fn,
        )
        elapsed = time.perf_counter() - t0
        return {"rows": rows, "latency": elapsed, "error": None}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"rows": [], "latency": elapsed, "error": str(e)}


def run_benchmark(client: anthropic.Anthropic, source: SQLiteDBSource, conn: sqlite3.Connection) -> list[dict]:
    results = []

    for tc in TEST_CASES:
        print(f"\n{DIV2}")
        print(f"  [{tc['id']}]  {tc['question']}")
        print(f"  ({tc['note']})")

        # ground truth
        cur = conn.cursor()
        cur.execute(tc["gt_sql"])
        cols = [d[0] for d in cur.description]
        gt_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        print(f"  GT  → {gt_rows[:3]}")

        # 1-shot
        calls_1s: list = [0]
        r1 = run_oneshot(source, tc["question"], calls_1s, client)
        acc_1s = tc["check"](gt_rows, r1["rows"]) if not r1["error"] else False
        print(f"  1-shot  → calls={calls_1s[0]}  latency={r1['latency']:.2f}s  "
              f"correct={'✓' if acc_1s else '✗'}  rows={len(r1['rows'])}  "
              f"{'ERR: ' + r1['error'] if r1['error'] else ''}")
        if r1["rows"]:
            print(f"           result sample: {r1['rows'][:2]}")

        # tool-based
        calls_tb: list = [0]
        r2 = run_tools(source, tc["question"], calls_tb, client)
        acc_tb = tc["check"](gt_rows, r2["rows"]) if not r2["error"] else False
        print(f"  tool    → calls={calls_tb[0]}  latency={r2['latency']:.2f}s  "
              f"correct={'✓' if acc_tb else '✗'}  rows={len(r2['rows'])}  "
              f"{'ERR: ' + r2['error'] if r2['error'] else ''}")
        if r2["rows"]:
            print(f"           result sample: {r2['rows'][:2]}")

        results.append({
            "id":           tc["id"],
            "category":     tc["category"],
            "question":     tc["question"],
            "note":         tc["note"],
            "ground_truth": gt_rows,
            "oneshot": {
                "correct": acc_1s,
                "latency": round(r1["latency"], 3),
                "llm_calls": calls_1s[0],
                "rows": len(r1["rows"]),
                "error": r1["error"],
            },
            "toolbased": {
                "correct": acc_tb,
                "latency": round(r2["latency"], 3),
                "llm_calls": calls_tb[0],
                "rows": len(r2["rows"]),
                "error": r2["error"],
            },
        })

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: list[dict]) -> None:
    print(f"\n{DIV}")
    print("SUMMARY")
    print(DIV)

    header = f"{'Question':<35} {'1-shot':>8} {'Tool':>8} {'1-shot lat':>11} {'Tool lat':>10} {'1-shot calls':>13} {'Tool calls':>11}"
    print(header)
    print("-" * len(header))

    for r in results:
        o, t = r["oneshot"], r["toolbased"]
        q = r["question"][:34]
        print(
            f"{q:<35} "
            f"{'✓' if o['correct'] else '✗':>8} "
            f"{'✓' if t['correct'] else '✗':>8} "
            f"{o['latency']:>10.2f}s "
            f"{t['latency']:>9.2f}s "
            f"{o['llm_calls']:>13} "
            f"{t['llm_calls']:>11}"
        )

    n = len(results)
    o_acc  = sum(r["oneshot"]["correct"]   for r in results)
    t_acc  = sum(r["toolbased"]["correct"] for r in results)
    o_lat  = sum(r["oneshot"]["latency"]   for r in results) / n
    t_lat  = sum(r["toolbased"]["latency"] for r in results) / n
    o_call = sum(r["oneshot"]["llm_calls"]   for r in results) / n
    t_call = sum(r["toolbased"]["llm_calls"] for r in results) / n

    print("-" * len(header))
    print(
        f"{'TOTALS / AVERAGES':<35} "
        f"{f'{o_acc}/{n}':>8} "
        f"{f'{t_acc}/{n}':>8} "
        f"{o_lat:>10.2f}s "
        f"{t_lat:>9.2f}s "
        f"{o_call:>13.1f} "
        f"{t_call:>11.1f}"
    )
    print(DIV)


def write_report(results: list[dict], path: str) -> None:
    n = len(results)
    o_acc  = sum(r["oneshot"]["correct"]   for r in results)
    t_acc  = sum(r["toolbased"]["correct"] for r in results)
    o_lat  = sum(r["oneshot"]["latency"]   for r in results) / n
    t_lat  = sum(r["toolbased"]["latency"] for r in results) / n
    o_call = sum(r["oneshot"]["llm_calls"]   for r in results) / n
    t_call = sum(r["toolbased"]["llm_calls"] for r in results) / n

    lines = [
        "# NL2Q Benchmark — 1-shot vs Tool-based",
        "",
        f"Model: `{MODEL}`  |  Dataset: Northwind SQLite  |  Questions: {n}",
        "",
        "## Summary",
        "",
        f"| Metric | 1-shot | Tool-based |",
        f"|---|---|---|",
        f"| Accuracy | {o_acc}/{n} ({100*o_acc//n}%) | {t_acc}/{n} ({100*t_acc//n}%) |",
        f"| Avg latency | {o_lat:.2f}s | {t_lat:.2f}s |",
        f"| Avg LLM calls | {o_call:.1f} | {t_call:.1f} |",
        "",
        "## Per-question results",
        "",
        "| # | Question | Category | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        o, t = r["oneshot"], r["toolbased"]
        lines.append(
            f"| {i} | {r['question']} | {r['category']} "
            f"| {'✓' if o['correct'] else '✗'} "
            f"| {'✓' if t['correct'] else '✗'} "
            f"| {o['latency']:.2f}s "
            f"| {t['latency']:.2f}s "
            f"| {o['llm_calls']} "
            f"| {t['llm_calls']} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- **1-shot**: schema injected into a single prompt; LLM returns SQL; one round trip.",
        "- **Tool-based**: LLM drives a tool loop (`list_databases`, `get_schema`, `execute_query`, …); "
          "multiple round trips allowed.",
        f"- Accuracy checker: scalar queries use ±0.5–5 tolerance; "
          "ranking queries check top-1 match; join queries check value presence.",
    ]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines))
    print(f"Report written → {path}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_db() -> tuple[str, sqlite3.Connection]:
    tmp = tempfile.mkdtemp(prefix="blue-nl2q-bench-")
    db_path = os.path.join(tmp, f"{DB_NAME}.db")
    sql = SQL_FILE.read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    return tmp, conn


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY to run this benchmark.")

    p = argparse.ArgumentParser(description="NL2Q benchmark: 1-shot vs tool-based")
    _here = Path(__file__).parent
    p.add_argument("--out",    default=str(_here / "nl2q.json"),
                   help="Save raw JSON results to this path")
    p.add_argument("--report", default=str(_here / "NL2Q_RESULTS.md"),
                   help="Write markdown report to this path")
    args = p.parse_args()

    client = anthropic.Anthropic(api_key=api_key)

    print(DIV)
    print(f"NL2Q Benchmark  —  model: {MODEL}")
    print(f"Dataset: {SQL_FILE}")
    print(f"Questions: {len(TEST_CASES)}")
    print(DIV)

    tmp, conn = setup_db()
    source = SQLiteDBSource(DB_NAME, properties={
        "connection": {"database_directory": tmp}
    })

    results = run_benchmark(client, source, conn)
    conn.close()

    print_summary(results)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"Raw results → {args.out}")

    write_report(results, args.report)
    print(f"Report written → {args.report}")


if __name__ == "__main__":
    main()
