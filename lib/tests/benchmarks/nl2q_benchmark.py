"""
NL2Q Benchmark — 1-shot NL2SQL vs Tool-based NL2Q.

Runs fixed question sets across multiple datasets (Northwind, Finance) through
both approaches and compares:
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

    # run a single dataset
    python3 lib/tests/benchmarks/nl2q_benchmark.py --dataset northwind
    python3 lib/tests/benchmarks/nl2q_benchmark.py --dataset finance
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

MODEL = "claude-haiku-4-5-20251001"
COLL  = "public"

_ROOT = Path(__file__).resolve().parents[3]

DIV  = "=" * 72
DIV2 = "-" * 72


# ---------------------------------------------------------------------------
# Checkers
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


# ---------------------------------------------------------------------------
# Northwind test cases
# ---------------------------------------------------------------------------

NORTHWIND_CASES = [
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
            JOIN products p   ON od.product_id  = p.product_id
            JOIN categories c ON p.category_id  = c.category_id
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
# Finance test cases
#
# The Czech banking dataset (BIRD benchmark) deliberately uses opaque column
# names (a2-a16 in district) and Czech domain codes (PRIJEM/VYDAJ, status
# A/B/C/D, Czech frequency strings).  This stress-tests schema grounding for
# 1-shot (raw column names, no hints) vs tool-based (can sample rows to
# disambiguate).
# ---------------------------------------------------------------------------

FINANCE_CASES = [
    {
        "id":       "female_clients",
        "category": "filter",
        "question": "How many female clients are there?",
        "gt_sql":   "SELECT COUNT(*) as count FROM client WHERE gender = 'F'",
        "check":    _scalar,
        "note":     "Basic gender filter",
    },
    {
        "id":       "avg_loan_amount",
        "category": "aggregation",
        "question": "What is the average loan amount?",
        "gt_sql":   "SELECT ROUND(AVG(amount), 2) as avg_amount FROM loan",
        "check":    lambda g, r: _scalar(g, r, tol=100.0),
        "note":     "AVG over loan table",
    },
    {
        "id":       "highest_salary_district",
        "category": "sort",
        "question": "Which district has the highest average salary?",
        "gt_sql":   "SELECT a2 as district_name, a11 as avg_salary FROM district ORDER BY a11 DESC LIMIT 1",
        "check":    _top1_match,
        "note":     "Opaque columns a2/a11 — requires schema grounding",
    },
    {
        "id":       "running_loans_ok",
        "category": "filter",
        "question": "How many loans are currently running with no problems?",
        "gt_sql":   "SELECT COUNT(*) as count FROM loan WHERE status = 'C'",
        "check":    _scalar,
        "note":     "Status code C — requires domain code knowledge",
    },
    {
        "id":       "total_credit_amount",
        "category": "aggregation",
        "question": "What is the total amount of all credit (incoming) transactions?",
        "gt_sql":   "SELECT SUM(amount) as total FROM trans WHERE type = 'PRIJEM'",
        "check":    lambda g, r: _scalar(g, r, tol=100.0),
        "note":     "Czech type code PRIJEM — requires code knowledge",
    },
    {
        "id":       "monthly_accounts",
        "category": "filter",
        "question": "How many accounts have a monthly statement frequency?",
        "gt_sql":   "SELECT COUNT(*) as count FROM account WHERE frequency = 'POPLATEK MESICNE'",
        "check":    _scalar,
        "note":     "Czech frequency string — requires code knowledge",
    },
    {
        "id":       "avg_loan_duration",
        "category": "aggregation",
        "question": "What is the average loan duration in months?",
        "gt_sql":   "SELECT ROUND(AVG(duration), 1) as avg_months FROM loan",
        "check":    lambda g, r: _scalar(g, r, tol=2.0),
        "note":     "Simple AVG — clean columns",
    },
    {
        "id":       "accounts_with_loan",
        "category": "existence",
        "question": "How many accounts have at least one loan?",
        "gt_sql":   "SELECT COUNT(DISTINCT account_id) as count FROM loan",
        "check":    _scalar,
        "note":     "Distinct count via subquery or join",
    },
    {
        "id":       "largest_transaction",
        "category": "sort",
        "question": "What is the largest single transaction amount?",
        "gt_sql":   "SELECT MAX(amount) as max_amount FROM trans",
        "check":    _scalar,
        "note":     "MAX over trans table",
    },
    {
        "id":       "accounts_no_transactions",
        "category": "existence",
        "question": "How many accounts have no transactions at all?",
        "gt_sql":   """
            SELECT COUNT(*) as count FROM account
            WHERE account_id NOT IN (SELECT DISTINCT account_id FROM trans)
        """,
        "check":    _scalar,
        "note":     "NOT IN subquery — existence check",
    },
]


# ---------------------------------------------------------------------------
# Dataset configs
# ---------------------------------------------------------------------------

DATASETS = [
    {
        "name":       "northwind",
        "db_name":    "northwind",
        "coll":       COLL,
        "sql_file":   _ROOT / "data" / "northwind_sqlite.sql",
        "test_cases": NORTHWIND_CASES,
    },
    {
        "name":       "finance",
        "db_name":    "finance",
        "coll":       COLL,
        "sql_file":   _ROOT / "data" / "finance_sqlite.sql",
        "test_cases": FINANCE_CASES,
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
# Runners
# ---------------------------------------------------------------------------

def run_oneshot(source: SQLiteDBSource, question: str, cfg: dict, call_counter: list, client) -> dict:
    llm_fn = make_oneshot_llm(client, call_counter)

    entities_dict = source.fetch_database_collection_entities(cfg["db_name"], cfg["coll"])
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
            database=cfg["db_name"],
            collection=cfg["coll"],
            schema=schema_dict,
            llm_fn=llm_fn,
        )
        elapsed = time.perf_counter() - t0
        return {"rows": rows, "latency": elapsed, "error": None}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"rows": [], "latency": elapsed, "error": str(e)}


def run_tools(source: SQLiteDBSource, question: str, cfg: dict, call_counter: list, client) -> dict:
    llm_fn = make_tools_llm(client, call_counter)

    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl_tools(
            question,
            database=cfg["db_name"],
            collection=cfg["coll"],
            llm_fn=llm_fn,
        )
        elapsed = time.perf_counter() - t0
        return {"rows": rows, "latency": elapsed, "error": None}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"rows": [], "latency": elapsed, "error": str(e)}


def run_dataset(client: anthropic.Anthropic, cfg: dict) -> list[dict]:
    """Set up the dataset, run all questions, return per-question result dicts."""
    tmp, conn, source = setup_dataset(cfg)
    results = []

    print(f"\n{DIV}")
    print(f"  Dataset: {cfg['name'].upper()}  ({len(cfg['test_cases'])} questions)")
    print(DIV)

    for tc in cfg["test_cases"]:
        print(f"\n{DIV2}")
        print(f"  [{tc['id']}]  {tc['question']}")
        print(f"  ({tc['note']})")

        cur = conn.cursor()
        cur.execute(tc["gt_sql"])
        cols = [d[0] for d in cur.description]
        gt_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        print(f"  GT  → {gt_rows[:3]}")

        calls_1s: list = [0]
        r1 = run_oneshot(source, tc["question"], cfg, calls_1s, client)
        acc_1s = tc["check"](gt_rows, r1["rows"]) if not r1["error"] else False
        print(
            f"  1-shot  → calls={calls_1s[0]}  latency={r1['latency']:.2f}s  "
            f"correct={'✓' if acc_1s else '✗'}  rows={len(r1['rows'])}  "
            f"{'ERR: ' + r1['error'] if r1['error'] else ''}"
        )
        if r1["rows"]:
            print(f"           result sample: {r1['rows'][:2]}")

        calls_tb: list = [0]
        r2 = run_tools(source, tc["question"], cfg, calls_tb, client)
        acc_tb = tc["check"](gt_rows, r2["rows"]) if not r2["error"] else False
        print(
            f"  tool    → calls={calls_tb[0]}  latency={r2['latency']:.2f}s  "
            f"correct={'✓' if acc_tb else '✗'}  rows={len(r2['rows'])}  "
            f"{'ERR: ' + r2['error'] if r2['error'] else ''}"
        )
        if r2["rows"]:
            print(f"           result sample: {r2['rows'][:2]}")

        results.append({
            "dataset":      cfg["name"],
            "id":           tc["id"],
            "category":     tc["category"],
            "question":     tc["question"],
            "note":         tc["note"],
            "ground_truth": gt_rows,
            "oneshot": {
                "correct":   acc_1s,
                "latency":   round(r1["latency"], 3),
                "llm_calls": calls_1s[0],
                "rows":      len(r1["rows"]),
                "error":     r1["error"],
            },
            "toolbased": {
                "correct":   acc_tb,
                "latency":   round(r2["latency"], 3),
                "llm_calls": calls_tb[0],
                "rows":      len(r2["rows"]),
                "error":     r2["error"],
            },
        })

    conn.close()
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _dataset_stats(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}
    return {
        "n":      n,
        "o_acc":  sum(r["oneshot"]["correct"]   for r in results),
        "t_acc":  sum(r["toolbased"]["correct"] for r in results),
        "o_lat":  sum(r["oneshot"]["latency"]   for r in results) / n,
        "t_lat":  sum(r["toolbased"]["latency"] for r in results) / n,
        "o_call": sum(r["oneshot"]["llm_calls"]   for r in results) / n,
        "t_call": sum(r["toolbased"]["llm_calls"] for r in results) / n,
    }


def print_summary(all_results: list[dict]) -> None:
    datasets = {}
    for r in all_results:
        datasets.setdefault(r["dataset"], []).append(r)

    header = (
        f"{'Question':<35} {'1-shot':>8} {'Tool':>8} "
        f"{'1-shot lat':>11} {'Tool lat':>10} "
        f"{'1-shot calls':>13} {'Tool calls':>11}"
    )

    for ds_name, ds_results in datasets.items():
        print(f"\n{DIV}")
        print(f"  {ds_name.upper()}")
        print(DIV)
        print(header)
        print("-" * len(header))
        for r in ds_results:
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
        s = _dataset_stats(ds_results)
        o_label = f"{s['o_acc']}/{s['n']}"
        t_label = f"{s['t_acc']}/{s['n']}"
        print("-" * len(header))
        print(
            f"{'DATASET TOTALS':<35} "
            f"{o_label:>8} "
            f"{t_label:>8} "
            f"{s['o_lat']:>10.2f}s "
            f"{s['t_lat']:>9.2f}s "
            f"{s['o_call']:>13.1f} "
            f"{s['t_call']:>11.1f}"
        )

    # overall
    s = _dataset_stats(all_results)
    print(f"\n{DIV}")
    print(f"OVERALL  ({s['n']} questions across {len(datasets)} datasets)")
    print(DIV)
    print(
        f"  1-shot   accuracy  {s['o_acc']}/{s['n']} ({100 * s['o_acc'] // s['n']}%)   "
        f"avg latency {s['o_lat']:.2f}s   avg calls {s['o_call']:.1f}"
    )
    print(
        f"  tool     accuracy  {s['t_acc']}/{s['n']} ({100 * s['t_acc'] // s['n']}%)   "
        f"avg latency {s['t_lat']:.2f}s   avg calls {s['t_call']:.1f}"
    )
    print(DIV)


def write_report(all_results: list[dict], path: str) -> None:
    datasets = {}
    for r in all_results:
        datasets.setdefault(r["dataset"], []).append(r)

    overall = _dataset_stats(all_results)
    n_ds = len(datasets)

    lines = [
        "# NL2Q Benchmark — 1-shot vs Tool-based",
        "",
        f"Model: `{MODEL}`  |  Datasets: {', '.join(datasets)}  |  Questions: {overall['n']}",
        "",
        "## Overall summary",
        "",
        "| Metric | 1-shot | Tool-based |",
        "|---|---|---|",
        f"| Accuracy | {overall['o_acc']}/{overall['n']} ({100 * overall['o_acc'] // overall['n']}%) "
        f"| {overall['t_acc']}/{overall['n']} ({100 * overall['t_acc'] // overall['n']}%) |",
        f"| Avg latency | {overall['o_lat']:.2f}s | {overall['t_lat']:.2f}s |",
        f"| Avg LLM calls | {overall['o_call']:.1f} | {overall['t_call']:.1f} |",
        "",
    ]

    for ds_name, ds_results in datasets.items():
        s = _dataset_stats(ds_results)
        lines += [
            f"## {ds_name.capitalize()} ({s['n']} questions)",
            "",
            "| Metric | 1-shot | Tool-based |",
            "|---|---|---|",
            f"| Accuracy | {s['o_acc']}/{s['n']} ({100 * s['o_acc'] // s['n']}%) "
            f"| {s['t_acc']}/{s['n']} ({100 * s['t_acc'] // s['n']}%) |",
            f"| Avg latency | {s['o_lat']:.2f}s | {s['t_lat']:.2f}s |",
            f"| Avg LLM calls | {s['o_call']:.1f} | {s['t_call']:.1f} |",
            "",
            "| # | Question | Category | Note | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(ds_results, 1):
            o, t = r["oneshot"], r["toolbased"]
            lines.append(
                f"| {i} | {r['question']} | {r['category']} | {r['note']} "
                f"| {'✓' if o['correct'] else '✗'} "
                f"| {'✓' if t['correct'] else '✗'} "
                f"| {o['latency']:.2f}s "
                f"| {t['latency']:.2f}s "
                f"| {o['llm_calls']} "
                f"| {t['llm_calls']} |"
            )
        lines.append("")

    lines += [
        "## Notes",
        "",
        "- **1-shot**: full schema injected into a single prompt; LLM returns SQL; one round trip.",
        "- **Tool-based**: LLM drives a tool loop (`list_databases`, `get_schema`, `execute_query`, …); "
          "multiple round trips; can explore schema and sample data before answering.",
        "- **Finance dataset**: uses opaque column names (`a2`–`a16`) and Czech domain codes "
          "(`PRIJEM`/`VYDAJ`, `POPLATEK MESICNE`, status `A`/`B`/`C`/`D`). "
          "1-shot receives raw column names with no hints; tool-based can query sample rows to disambiguate.",
        "- Accuracy checkers: scalar queries use ±0.5–100 tolerance; ranking queries check top-1 match; "
          "join queries check value presence.",
    ]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines))
    print(f"Report written → {path}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_dataset(cfg: dict) -> tuple[str, sqlite3.Connection, SQLiteDBSource]:
    tmp = tempfile.mkdtemp(prefix=f"blue-nl2q-{cfg['name']}-")
    db_path = os.path.join(tmp, f"{cfg['db_name']}.db")
    sql = Path(cfg["sql_file"]).read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    source = SQLiteDBSource(cfg["db_name"], properties={"connection": {"database_directory": tmp}})
    return tmp, conn, source


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY to run this benchmark.")

    p = argparse.ArgumentParser(description="NL2Q benchmark: 1-shot vs tool-based")
    _here = Path(__file__).parent
    p.add_argument("--out",     default=str(_here / "nl2q.json"),
                   help="Save raw JSON results to this path")
    p.add_argument("--report",  default=str(_here / "NL2Q_RESULTS.md"),
                   help="Write markdown report to this path")
    p.add_argument("--dataset", default=None,
                   help="Run only this dataset (northwind or finance). Default: all.")
    args = p.parse_args()

    client = anthropic.Anthropic(api_key=api_key)

    datasets = DATASETS
    if args.dataset:
        datasets = [d for d in DATASETS if d["name"] == args.dataset]
        if not datasets:
            raise SystemExit(f"Unknown dataset '{args.dataset}'. Choose: {[d['name'] for d in DATASETS]}")

    total_q = sum(len(d["test_cases"]) for d in datasets)
    print(DIV)
    print(f"NL2Q Benchmark  —  model: {MODEL}")
    print(f"Datasets: {[d['name'] for d in datasets]}  |  Questions: {total_q}")
    print(DIV)

    all_results: list[dict] = []
    for cfg in datasets:
        all_results.extend(run_dataset(client, cfg))

    print_summary(all_results)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(all_results, indent=2))
    print(f"Raw results → {args.out}")

    write_report(all_results, args.report)


if __name__ == "__main__":
    main()
