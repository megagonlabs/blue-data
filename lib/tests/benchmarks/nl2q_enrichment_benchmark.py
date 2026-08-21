"""
NL2Q Enrichment Benchmark — 2×2 matrix: enrichment × querying mode.

Compares four conditions against the Finance (Czech banking) dataset:

  1. baseline-1shot   — raw schema, 1-shot prompt (no enrichment, no tool loop)
  2. enriched-1shot   — enriched schema (value_semantics injected into prompt), 1-shot
  3. baseline-tools   — tool loop with no enrichment context
  4. enriched-tools   — tool loop + registry get_enriched_metadata tool

The Finance dataset is the primary stress test because it uses opaque column
names (a2-a16 in district) and Czech domain codes (PRIJEM/VYDAJ, POPLATEK
MESICNE, status A/B/C/D) that are invisible to the LLM without enrichment.

Usage
-----
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 lib/tests/benchmarks/nl2q_enrichment_benchmark.py

    # Finance only (default) or add Northwind
    python3 lib/tests/benchmarks/nl2q_enrichment_benchmark.py --dataset finance
    python3 lib/tests/benchmarks/nl2q_enrichment_benchmark.py --dataset all

    # override output paths
    python3 lib/tests/benchmarks/nl2q_enrichment_benchmark.py \\
        --out enrichment_nl2q.json \\
        --report ENRICHMENT_NL2Q_RESULTS.md
"""
from __future__ import annotations

import argparse
import json
import os
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
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-haiku-4-5-20251001"
COLL  = "public"

_ROOT = Path(__file__).resolve().parents[3]

DIV  = "=" * 72
DIV2 = "-" * 72

CONDITIONS = ["baseline_1shot", "enriched_1shot", "baseline_tools", "enriched_tools"]

CONDITION_LABELS = {
    "baseline_1shot":  "Baseline 1-shot",
    "enriched_1shot":  "Enriched 1-shot",
    "baseline_tools":  "Baseline tools",
    "enriched_tools":  "Enriched tools",
}


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def _scalar(gt_rows: list, res_rows: list, tol: float = 0.5) -> bool:
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
    if not gt_rows or not res_rows:
        return False
    gt_vals = {str(v).lower().strip() for v in gt_rows[0].values() if v is not None}
    res_vals = {str(v).lower().strip() for row in res_rows for v in row.values() if v is not None}
    return bool(gt_vals & res_vals)


def _top1_match(gt_rows: list, res_rows: list) -> bool:
    if not gt_rows or not res_rows:
        return False
    gt_vals = {str(v).lower().strip() for v in gt_rows[0].values() if v is not None}
    res_vals = {str(v).lower().strip() for v in res_rows[0].values() if v is not None}
    return bool(gt_vals & res_vals)


# ---------------------------------------------------------------------------
# Finance test cases
# ---------------------------------------------------------------------------

FINANCE_CASES = [
    {
        "id":       "female_clients",
        "category": "filter",
        "question": "How many female clients are there?",
        "gt_sql":   "SELECT COUNT(*) as count FROM client WHERE gender = 'F'",
        "check":    _scalar,
        "note":     "Basic gender filter",
        "enrichment_sensitive": False,
    },
    {
        "id":       "avg_loan_amount",
        "category": "aggregation",
        "question": "What is the average loan amount?",
        "gt_sql":   "SELECT ROUND(AVG(amount), 2) as avg_amount FROM loan",
        "check":    lambda g, r: _scalar(g, r, tol=100.0),
        "note":     "AVG over loan table",
        "enrichment_sensitive": False,
    },
    {
        "id":       "highest_salary_district",
        "category": "sort",
        "question": "Which district has the highest average salary?",
        "gt_sql":   "SELECT a2 as district_name, a11 as avg_salary FROM district ORDER BY a11 DESC LIMIT 1",
        "check":    _top1_match,
        "note":     "Opaque columns a2/a11 — enrichment reveals meaning",
        "enrichment_sensitive": True,
    },
    {
        "id":       "running_loans_ok",
        "category": "filter",
        "question": "How many loans are currently running with no problems?",
        "gt_sql":   "SELECT COUNT(*) as count FROM loan WHERE status = 'C'",
        "check":    _scalar,
        "note":     "Status code C — enrichment shows enum values",
        "enrichment_sensitive": True,
    },
    {
        "id":       "total_credit_amount",
        "category": "aggregation",
        "question": "What is the total amount of all credit (incoming) transactions?",
        "gt_sql":   "SELECT SUM(amount) as total FROM trans WHERE type = 'PRIJEM'",
        "check":    lambda g, r: _scalar(g, r, tol=100.0),
        "note":     "Czech type code PRIJEM — enrichment shows enum values",
        "enrichment_sensitive": True,
    },
    {
        "id":       "monthly_accounts",
        "category": "filter",
        "question": "How many accounts have a monthly statement frequency?",
        "gt_sql":   "SELECT COUNT(*) as count FROM account WHERE frequency = 'POPLATEK MESICNE'",
        "check":    _scalar,
        "note":     "Czech frequency string — enrichment shows enum values",
        "enrichment_sensitive": True,
    },
    {
        "id":       "avg_loan_duration",
        "category": "aggregation",
        "question": "What is the average loan duration in months?",
        "gt_sql":   "SELECT ROUND(AVG(duration), 1) as avg_months FROM loan",
        "check":    lambda g, r: _scalar(g, r, tol=2.0),
        "note":     "Simple AVG — clean columns",
        "enrichment_sensitive": False,
    },
    {
        "id":       "accounts_with_loan",
        "category": "existence",
        "question": "How many accounts have at least one loan?",
        "gt_sql":   "SELECT COUNT(DISTINCT account_id) as count FROM loan",
        "check":    _scalar,
        "note":     "Distinct count",
        "enrichment_sensitive": False,
    },
    {
        "id":       "largest_transaction",
        "category": "sort",
        "question": "What is the largest single transaction amount?",
        "gt_sql":   "SELECT MAX(amount) as max_amount FROM trans",
        "check":    _scalar,
        "note":     "MAX over trans table",
        "enrichment_sensitive": False,
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
        "enrichment_sensitive": False,
    },
    # --- process semantics: loan lifecycle ---
    {
        "id":       "loans_in_trouble",
        "category": "filter",
        "question": "How many loans have problems — either currently running with debt or finished but not fully paid off?",
        "gt_sql":   "SELECT COUNT(*) as count FROM loan WHERE status IN ('B', 'D')",
        "check":    _scalar,
        "note":     "Status B (finished unpaid) + D (running in debt) — process semantics",
        "enrichment_sensitive": True,
    },
    {
        "id":       "finished_loans_loss",
        "category": "filter",
        "question": "How many loans were finished but the debt was not paid off?",
        "gt_sql":   "SELECT COUNT(*) as count FROM loan WHERE status = 'B'",
        "check":    _scalar,
        "note":     "Status B — finished with unpaid balance, process semantics",
        "enrichment_sensitive": True,
    },
    # --- process semantics: transaction operation codes ---
    {
        "id":       "card_withdrawals",
        "category": "filter",
        "question": "How many credit card withdrawal transactions are there?",
        "gt_sql":   "SELECT COUNT(*) as count FROM trans WHERE operation = 'VYBER KARTOU'",
        "check":    _scalar,
        "note":     "Czech operation code VYBER KARTOU — process semantics",
        "enrichment_sensitive": True,
    },
    {
        "id":       "outgoing_transfers",
        "category": "filter",
        "question": "How many outgoing bank transfer transactions are there?",
        "gt_sql":   "SELECT COUNT(*) as count FROM trans WHERE operation = 'PREVOD NA UCET'",
        "check":    _scalar,
        "note":     "Czech operation code PREVOD NA UCET — process semantics",
        "enrichment_sensitive": True,
    },
    # --- process semantics: payment category (k_symbol) ---
    {
        "id":       "total_loan_repayments",
        "category": "aggregation",
        "question": "What is the total amount of loan repayment transactions?",
        "gt_sql":   "SELECT SUM(amount) as total FROM trans WHERE k_symbol = 'UVER'",
        "check":    lambda g, r: _scalar(g, r, tol=500.0),
        "note":     "k_symbol UVER (loan payment) — process semantics",
        "enrichment_sensitive": True,
    },
    {
        "id":       "penalty_interest_accounts",
        "category": "existence",
        "question": "How many accounts have ever been charged penalty interest?",
        "gt_sql":   "SELECT COUNT(DISTINCT account_id) as count FROM trans WHERE k_symbol = 'SANKC. UROK'",
        "check":    _scalar,
        "note":     "k_symbol SANKC. UROK (penalty interest) — process semantics",
        "enrichment_sensitive": True,
    },
    {
        "id":       "pension_credits",
        "category": "filter",
        "question": "How many transactions are pension income credits?",
        "gt_sql":   "SELECT COUNT(*) as count FROM trans WHERE k_symbol = 'DUCHOD' AND type = 'PRIJEM'",
        "check":    _scalar,
        "note":     "k_symbol DUCHOD + type PRIJEM — double process semantics",
        "enrichment_sensitive": True,
    },
    # --- opaque district columns ---
    {
        "id":       "avg_unemployment_1996",
        "category": "aggregation",
        "question": "What is the average unemployment rate across districts in 1996?",
        "gt_sql":   "SELECT ROUND(AVG(a13), 2) as avg_unemployment FROM district",
        "check":    lambda g, r: _scalar(g, r, tol=0.5),
        "note":     "Opaque column a13 (unemployment 1996) — requires schema grounding",
        "enrichment_sensitive": True,
    },
    {
        "id":       "total_population",
        "category": "aggregation",
        "question": "What is the total population across all districts?",
        "gt_sql":   "SELECT SUM(a4) as total_population FROM district",
        "check":    lambda g, r: _scalar(g, r, tol=1000.0),
        "note":     "Opaque column a4 (number of inhabitants) — requires schema grounding",
        "enrichment_sensitive": True,
    },
    # --- non-sensitive control ---
    {
        "id":       "male_clients",
        "category": "filter",
        "question": "How many male clients are there?",
        "gt_sql":   "SELECT COUNT(*) as count FROM client WHERE gender = 'M'",
        "check":    _scalar,
        "note":     "Basic gender filter — control (no enrichment needed)",
        "enrichment_sensitive": False,
    },
]


NORTHWIND_CASES = [
    {
        "id":       "count_by_country",
        "category": "filter",
        "question": "How many customers are from Germany?",
        "gt_sql":   "SELECT COUNT(*) as count FROM customers WHERE country = 'Germany'",
        "check":    _scalar,
        "note":     "Simple WHERE + COUNT",
        "enrichment_sensitive": False,
    },
    {
        "id":       "avg_freight",
        "category": "aggregation",
        "question": "What is the average freight cost across all orders?",
        "gt_sql":   "SELECT ROUND(AVG(freight), 2) as avg_freight FROM orders",
        "check":    lambda g, r: _scalar(g, r, tol=2.0),
        "note":     "AVG aggregation",
        "enrichment_sensitive": False,
    },
    {
        "id":       "discontinued_count",
        "category": "filter",
        "question": "How many products are discontinued?",
        "gt_sql":   "SELECT COUNT(*) as count FROM products WHERE discontinued = 1",
        "check":    _scalar,
        "note":     "Boolean filter + COUNT",
        "enrichment_sensitive": False,
    },
    {
        "id":       "top_expensive",
        "category": "sort",
        "question": "What is the most expensive product?",
        "gt_sql":   "SELECT product_name, unit_price FROM products ORDER BY unit_price DESC LIMIT 1",
        "check":    _top1_match,
        "note":     "ORDER BY + LIMIT 1",
        "enrichment_sensitive": False,
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
        "note":     "JOIN + GROUP BY + ORDER BY",
        "enrichment_sensitive": False,
    },
    {
        "id":       "beverages_count",
        "category": "join",
        "question": "How many products are in the Beverages category?",
        "gt_sql":   """
            SELECT COUNT(*) as count FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE c.category_name = 'Beverages'
        """,
        "check":    _scalar,
        "note":     "JOIN + category filter",
        "enrichment_sensitive": False,
    },
    {
        "id":       "uk_suppliers",
        "category": "filter",
        "question": "How many suppliers are from the UK?",
        "gt_sql":   "SELECT COUNT(*) as count FROM suppliers WHERE country = 'UK'",
        "check":    _scalar,
        "note":     "Simple country filter on suppliers",
        "enrichment_sensitive": False,
    },
    {
        "id":       "london_employees",
        "category": "filter",
        "question": "How many employees are based in London?",
        "gt_sql":   "SELECT COUNT(*) as count FROM employees WHERE city = 'London'",
        "check":    _scalar,
        "note":     "City filter on employees",
        "enrichment_sensitive": False,
    },
    {
        "id":       "orders_to_france",
        "category": "filter",
        "question": "How many orders were shipped to France?",
        "gt_sql":   "SELECT COUNT(*) as count FROM orders WHERE ship_country = 'France'",
        "check":    _scalar,
        "note":     "Ship country filter",
        "enrichment_sensitive": False,
    },
    {
        "id":       "avg_discount",
        "category": "aggregation",
        "question": "What is the average discount applied across all order lines?",
        "gt_sql":   "SELECT ROUND(AVG(discount), 4) as avg_discount FROM order_details",
        "check":    lambda g, r: _scalar(g, r, tol=0.05),
        "note":     "AVG on order_details discount",
        "enrichment_sensitive": False,
    },
    {
        "id":       "most_ordered_product",
        "category": "join",
        "question": "Which product appears in the most orders?",
        "gt_sql":   """
            SELECT p.product_name, COUNT(*) as order_count
            FROM order_details od JOIN products p ON od.product_id = p.product_id
            GROUP BY od.product_id ORDER BY order_count DESC LIMIT 1
        """,
        "check":    _top1_match,
        "note":     "JOIN + GROUP BY + top-1",
        "enrichment_sensitive": False,
    },
    {
        "id":       "total_quantity_sold",
        "category": "aggregation",
        "question": "What is the total quantity of items sold across all orders?",
        "gt_sql":   "SELECT SUM(quantity) as total_quantity FROM order_details",
        "check":    _scalar,
        "note":     "SUM on order_details quantity",
        "enrichment_sensitive": False,
    },
    {
        "id":       "japan_suppliers",
        "category": "filter",
        "question": "How many suppliers are from Japan?",
        "gt_sql":   "SELECT COUNT(*) as count FROM suppliers WHERE country = 'Japan'",
        "check":    _scalar,
        "note":     "Country filter on suppliers",
        "enrichment_sensitive": False,
    },
    {
        "id":       "seafood_products",
        "category": "join",
        "question": "How many seafood products are there?",
        "gt_sql":   """
            SELECT COUNT(*) as count FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE c.category_name = 'Seafood'
        """,
        "check":    _scalar,
        "note":     "JOIN + category filter",
        "enrichment_sensitive": False,
    },
    {
        "id":       "highest_stock_product",
        "category": "sort",
        "question": "Which product has the most units in stock?",
        "gt_sql":   "SELECT product_name, units_in_stock FROM products ORDER BY units_in_stock DESC LIMIT 1",
        "check":    _top1_match,
        "note":     "ORDER BY + LIMIT 1 on stock",
        "enrichment_sensitive": False,
    },
]


DATASETS = {
    "finance": {
        "name":       "finance",
        "db_name":    "finance",
        "coll":       COLL,
        "sql_file":   _ROOT / "data" / "finance_sqlite.sql",
        "test_cases": FINANCE_CASES,
    },
    "northwind": {
        "name":       "northwind",
        "db_name":    "northwind",
        "coll":       COLL,
        "sql_file":   _ROOT / "data" / "northwind_sqlite.sql",
        "test_cases": NORTHWIND_CASES,
    },
}


# ---------------------------------------------------------------------------
# LLM factories
# ---------------------------------------------------------------------------

def make_oneshot_llm(client: anthropic.Anthropic, counter: list) -> Any:
    def llm_fn(prompt: str) -> str:
        counter[0] += 1
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


def make_tools_llm(client: anthropic.Anthropic, counter: list) -> Any:
    def llm_fn(messages, tools, system=None):
        counter[0] += 1
        kwargs: dict = dict(model=MODEL, max_tokens=1024, tools=tools, messages=messages)
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return {
            "stop_reason": resp.stop_reason,
            "content":     [b.model_dump() for b in resp.content],
        }
    return llm_fn


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_source(cfg: dict) -> tuple[str, sqlite3.Connection, SQLiteDBSource]:
    """Create a temp SQLite DB from the SQL file, return (tmp_dir, conn, source)."""
    tmp = tempfile.mkdtemp(prefix=f"blue-enrich-{cfg['name']}-")
    db_path = os.path.join(tmp, f"{cfg['db_name']}.db")
    sql = Path(cfg["sql_file"]).read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    source = SQLiteDBSource(
        cfg["db_name"],
        properties={"connection": {"database_directory": tmp}},
    )
    return tmp, conn, source


def setup_registry(cfg: dict, source: SQLiteDBSource, llm_fn) -> DataRegistry:
    """Create a DataRegistry, register+sync the source, and run Layer 1 enrichment."""
    registry = DataRegistry(
        metadata_enricher=MetaData(llm_fn=llm_fn),
    )
    source_name = cfg["db_name"]
    registry.register_source(source)
    registry.sync_source(source_name, recursive=True)

    # collect stats so SemanticTypeInferencer has sample values to work with
    for db_rec in registry.list_source_databases(source_name):
        db = db_rec["name"]
        for coll_rec in registry.list_database_collections(source_name, db):
            coll = coll_rec["name"]
            for entity_rec in registry.list_collection_entities(source_name, db, coll):
                entity = entity_rec["name"]
                for attr_rec in registry.list_entity_attributes(source_name, db, coll, entity):
                    attr = attr_rec["name"]
                    registry.collect_source_database_collection_entity_attribute_stats(
                        source_name, db, coll, entity, attr
                    )

    # Layer 1: deterministic semantic type inference
    registry.enrich_source(source_name)

    return registry


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def _gt_rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def run_baseline_oneshot(
    source: SQLiteDBSource,
    question: str,
    cfg: dict,
    counter: list,
    client: anthropic.Anthropic,
) -> dict:
    """1-shot with raw schema — no enrichment."""
    llm_fn = make_oneshot_llm(client, counter)
    entities_dict = source.fetch_database_collection_entities(cfg["db_name"], cfg["coll"])
    schema = {
        "entities": [
            {"name": e["name"], "attributes": e.get("contents", {}).get("attributes", {})}
            for e in entities_dict.values()
        ]
    }
    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl(
            question,
            database=cfg["db_name"],
            collection=cfg["coll"],
            schema=schema,
            llm_fn=llm_fn,
        )
        return {"rows": rows, "latency": time.perf_counter() - t0, "error": None}
    except Exception as exc:
        return {"rows": [], "latency": time.perf_counter() - t0, "error": str(exc)}


def run_enriched_oneshot(
    source: SQLiteDBSource,
    registry: DataRegistry,
    question: str,
    cfg: dict,
    counter: list,
    client: anthropic.Anthropic,
) -> dict:
    """1-shot with enriched schema (value_semantics injected into prompt)."""
    llm_fn = make_oneshot_llm(client, counter)
    schema = registry.build_schema_for_nl(
        cfg["db_name"], cfg["db_name"], cfg["coll"], include_metadata=True
    )
    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl(
            question,
            database=cfg["db_name"],
            collection=cfg["coll"],
            schema=schema,
            llm_fn=llm_fn,
        )
        return {"rows": rows, "latency": time.perf_counter() - t0, "error": None}
    except Exception as exc:
        return {"rows": [], "latency": time.perf_counter() - t0, "error": str(exc)}


def run_baseline_tools(
    source: SQLiteDBSource,
    question: str,
    cfg: dict,
    counter: list,
    client: anthropic.Anthropic,
) -> dict:
    """Tool loop without enrichment — source-level only."""
    llm_fn = make_tools_llm(client, counter)
    t0 = time.perf_counter()
    try:
        rows = source.execute_query_nl_tools(
            question,
            database=cfg["db_name"],
            collection=cfg["coll"],
            llm_fn=llm_fn,
        )
        return {"rows": rows, "latency": time.perf_counter() - t0, "error": None}
    except Exception as exc:
        return {"rows": [], "latency": time.perf_counter() - t0, "error": str(exc)}


def run_enriched_tools(
    registry: DataRegistry,
    question: str,
    cfg: dict,
    counter: list,
    client: anthropic.Anthropic,
) -> dict:
    """Tool loop via DataRegistry — get_enriched_metadata tool available."""
    # patch registry's llm_fn so it uses the counter-instrumented one
    tools_llm = make_tools_llm(client, counter)
    registry.metadata_enricher._llm_fn = tools_llm
    t0 = time.perf_counter()
    try:
        rows = registry.execute_query_nl_tools(
            cfg["db_name"],
            question,
            database=cfg["db_name"],
            collection=cfg["coll"],
        )
        return {"rows": rows, "latency": time.perf_counter() - t0, "error": None}
    except Exception as exc:
        return {"rows": [], "latency": time.perf_counter() - t0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

def run_dataset(client: anthropic.Anthropic, cfg: dict) -> list[dict]:
    print(f"\n{DIV}")
    print(f"  Dataset: {cfg['name'].upper()}  ({len(cfg['test_cases'])} questions)")
    print(f"  Setting up DB + registry + enrichment …")

    tmp, conn, source = setup_source(cfg)

    # The LLM callable for the registry enricher — only used by enriched_tools
    # at query time (Layer 1 is deterministic and needs no LLM).
    def _placeholder_llm(messages, tools, system=None):
        raise RuntimeError("LLM called during setup — unexpected")

    registry = setup_registry(cfg, source, _placeholder_llm)
    print(f"  Registry ready. Running questions …")
    print(DIV)

    results = []
    for tc in cfg["test_cases"]:
        print(f"\n{DIV2}")
        print(f"  [{tc['id']}]  {tc['question']}")
        print(f"  ({tc['note']})")
        gt = _gt_rows(conn, tc["gt_sql"])
        print(f"  GT  → {gt[:3]}")

        row: dict = {
            "dataset":   cfg["name"],
            "id":        tc["id"],
            "category":  tc["category"],
            "question":  tc["question"],
            "note":      tc["note"],
            "enrichment_sensitive": tc.get("enrichment_sensitive", False),
            "ground_truth": gt,
        }

        for cond in CONDITIONS:
            ctr: list = [0]

            if cond == "baseline_1shot":
                r = run_baseline_oneshot(source, tc["question"], cfg, ctr, client)
            elif cond == "enriched_1shot":
                r = run_enriched_oneshot(source, registry, tc["question"], cfg, ctr, client)
            elif cond == "baseline_tools":
                r = run_baseline_tools(source, tc["question"], cfg, ctr, client)
            else:  # enriched_tools
                r = run_enriched_tools(registry, tc["question"], cfg, ctr, client)

            correct = tc["check"](gt, r["rows"]) if not r["error"] else False
            label = CONDITION_LABELS[cond]
            print(
                f"  {label:<20} → calls={ctr[0]}  lat={r['latency']:.2f}s  "
                f"{'✓' if correct else '✗'}  rows={len(r['rows'])}"
                + (f"  ERR: {r['error']}" if r["error"] else "")
            )
            if r["rows"]:
                print(f"    sample: {r['rows'][:2]}")

            row[cond] = {
                "correct":   correct,
                "latency":   round(r["latency"], 3),
                "llm_calls": ctr[0],
                "rows":      len(r["rows"]),
                "error":     r["error"],
            }

        results.append(row)

    conn.close()
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _stats(results: list[dict], cond: str) -> dict:
    n = len(results)
    if n == 0:
        return {}
    return {
        "n":    n,
        "acc":  sum(r[cond]["correct"]   for r in results),
        "lat":  sum(r[cond]["latency"]   for r in results) / n,
        "calls": sum(r[cond]["llm_calls"] for r in results) / n,
    }


def print_summary(all_results: list[dict]) -> None:
    datasets: dict[str, list] = {}
    for r in all_results:
        datasets.setdefault(r["dataset"], []).append(r)

    for ds_name, ds_results in datasets.items():
        n = len(ds_results)
        print(f"\n{DIV}\n  {ds_name.upper()} — per-question results\n{DIV}")
        header = (
            f"{'Question':<36} {'Sens':>4}  "
            + "  ".join(f"{CONDITION_LABELS[c]:>18}" for c in CONDITIONS)
        )
        print(header)
        print("-" * len(header))
        for r in ds_results:
            parts = [f"{'✓' if r[c]['correct'] else '✗'} {r[c]['llm_calls']}call {r[c]['latency']:.1f}s" for c in CONDITIONS]
            sens = "★" if r["enrichment_sensitive"] else " "
            print(f"{r['question'][:35]:<36} {sens:>4}  " + "  ".join(f"{p:>18}" for p in parts))

        print(f"\n{DIV}\n  {ds_name.upper()} — condition summary\n{DIV}")
        print(f"{'Condition':<22}  {'Accuracy':>10}  {'Avg latency':>12}  {'Avg calls':>10}")
        print("-" * 58)
        for cond in CONDITIONS:
            s = _stats(ds_results, cond)
            pct = 100 * s["acc"] // s["n"]
            print(
                f"{CONDITION_LABELS[cond]:<22}  {s['acc']}/{s['n']} ({pct:3}%)"
                f"  {s['lat']:>10.2f}s  {s['calls']:>10.1f}"
            )

        # enrichment-sensitive sub-slice
        sens = [r for r in ds_results if r.get("enrichment_sensitive")]
        if sens:
            print(f"\n  Enrichment-sensitive questions only ({len(sens)}):")
            print(f"  {'Condition':<22}  {'Accuracy':>10}")
            for cond in CONDITIONS:
                s = _stats(sens, cond)
                pct = 100 * s["acc"] // s["n"]
                print(f"  {CONDITION_LABELS[cond]:<22}  {s['acc']}/{s['n']} ({pct:3}%)")


def write_report(all_results: list[dict], path: str) -> None:
    datasets: dict[str, list] = {}
    for r in all_results:
        datasets.setdefault(r["dataset"], []).append(r)

    total_n = len(all_results)
    lines = [
        "# NL2Q Enrichment Benchmark — 2×2 Matrix",
        "",
        f"Model: `{MODEL}`  |  Total questions: {total_n}",
        "",
        "## Conditions",
        "",
        "| Label | Description |",
        "|---|---|",
        "| Baseline 1-shot | Raw schema injected into a single prompt; no enrichment |",
        "| Enriched 1-shot | Enriched schema with semantic types and sample values injected |",
        "| Baseline tools  | Tool loop (list, get_schema, execute_query); no enrichment |",
        "| Enriched tools  | Tool loop + `get_enriched_metadata` registry tool available |",
        "",
    ]

    for ds_name, ds_results in datasets.items():
        n = len(ds_results)
        lines += [
            f"## {ds_name.capitalize()} ({n} questions)",
            "",
            "### Condition summary",
            "",
            "| Condition | Accuracy | Avg latency | Avg LLM calls |",
            "|---|---|---|---|",
        ]
        for cond in CONDITIONS:
            s = _stats(ds_results, cond)
            pct = 100 * s["acc"] // s["n"]
            lines.append(
                f"| {CONDITION_LABELS[cond]} | {s['acc']}/{s['n']} ({pct}%) "
                f"| {s['lat']:.2f}s | {s['calls']:.1f} |"
            )

        sens = [r for r in ds_results if r.get("enrichment_sensitive")]
        if sens:
            lines += [
                "",
                f"### Enrichment-sensitive questions ({len(sens)} of {n})",
                "",
                "| Condition | Accuracy |",
                "|---|---|",
            ]
            for cond in CONDITIONS:
                s = _stats(sens, cond)
                pct = 100 * s["acc"] // s["n"]
                lines.append(f"| {CONDITION_LABELS[cond]} | {s['acc']}/{s['n']} ({pct}%) |")

        lines += [
            "",
            "### Per-question results",
            "",
            "| # | Question | Sensitive | " + " | ".join(CONDITION_LABELS[c] for c in CONDITIONS) + " |",
            "|---|---|---| " + " | ".join("---" for _ in CONDITIONS) + " |",
        ]
        for i, r in enumerate(ds_results, 1):
            sens_mark = "★" if r["enrichment_sensitive"] else ""
            cells = []
            for cond in CONDITIONS:
                c = r[cond]
                mark = "✓" if c["correct"] else "✗"
                cells.append(f"{mark} ({c['llm_calls']} calls, {c['latency']:.1f}s)")
            lines.append(f"| {i} | {r['question']} | {sens_mark} | " + " | ".join(cells) + " |")

        lines.append("")

    lines += [
        "## Notes",
        "",
        "- **★ enrichment-sensitive**: questions where opaque columns or domain codes make "
          "the correct answer hard to reach without external hints.",
        "- **Baseline 1-shot**: the LLM receives only column names and SQL types — no sample "
          "values, no semantic labels.",
        "- **Enriched 1-shot**: the schema prompt includes `semantic_type` and up to 5 "
          "`examples` from Layer 1 deterministic enrichment (SemanticTypeInferencer).",
        "- **Baseline tools**: the tool loop can call `get_sample` and `get_column_stats` to "
          "discover values at query time, but the registry is not available.",
        "- **Enriched tools**: the tool loop additionally has `get_enriched_metadata` which "
          "returns pre-computed value_semantics and metadata from the registry.",
        "- Layer 1 enrichment is fully deterministic (no LLM calls at enrichment time). "
          "Only querying incurs LLM cost.",
    ]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines))
    print(f"Report written → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY to run this benchmark.")

    _here = Path(__file__).parent
    p = argparse.ArgumentParser(
        description="NL2Q enrichment benchmark: 2×2 matrix (enrichment × querying mode)"
    )
    p.add_argument(
        "--dataset",
        default="all",
        choices=["finance", "northwind", "all"],
        help="Dataset to run (default: all)",
    )
    p.add_argument(
        "--out",
        default=str(_here / "nl2q_enrichment.json"),
        help="Save raw JSON results here",
    )
    p.add_argument(
        "--report",
        default=str(_here / "ENRICHMENT_NL2Q_RESULTS.md"),
        help="Write markdown report here",
    )
    args = p.parse_args()

    client = anthropic.Anthropic(api_key=api_key)

    if args.dataset == "all":
        cfgs = list(DATASETS.values())
    else:
        cfgs = [DATASETS[args.dataset]]

    total_q = sum(len(c["test_cases"]) for c in cfgs)
    print(DIV)
    print(f"NL2Q Enrichment Benchmark  —  model: {MODEL}")
    print(f"Conditions: {', '.join(CONDITION_LABELS.values())}")
    print(f"Datasets: {[c['name'] for c in cfgs]}  |  Questions: {total_q}")
    print(DIV)

    all_results: list[dict] = []
    for cfg in cfgs:
        all_results.extend(run_dataset(client, cfg))

    print_summary(all_results)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(all_results, indent=2))
    print(f"Raw results → {args.out}")

    write_report(all_results, args.report)


if __name__ == "__main__":
    main()
