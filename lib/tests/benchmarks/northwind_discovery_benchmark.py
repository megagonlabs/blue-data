"""
Northwind data discovery benchmark.

Tests whether search_records surfaces the correct entities and attributes
to answer real analytical questions about the Northwind e-commerce dataset.

Conditions:
  keyword  — BM25 only; always runs, no API key needed
  hybrid   — BM25 + OpenAI text-embedding-3-small; runs when OPENAI_API_KEY is set

Scoring: Hit@1, Hit@3, Hit@5, MRR against manually curated ground truth.

Dataset : data/northwind_sqlite.sql  (categories, suppliers, customers,
                                      employees, products, orders, order_details)
Queries : data/northwind_discovery_queries.json  (20 analytical questions)

Query categories:
  aggregation (3) — counting, summing, averaging over a single entity
  filter      (4) — finding records matching a coded or threshold condition
  join        (8) — intent spans multiple entities via foreign keys
  temporal    (2) — date-based grouping or ordering
  existence   (3) — "never ordered", "no associated record" queries

Usage:
    # keyword-only (no API key needed)
    python3 lib/tests/benchmarks/northwind_discovery_benchmark.py

    # keyword + hybrid
    export OPENAI_API_KEY=sk-...
    python3 lib/tests/benchmarks/northwind_discovery_benchmark.py

    # save results and report
    python3 lib/tests/benchmarks/northwind_discovery_benchmark.py \\
        --out results/northwind_discovery.json --report
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _discovery_runner import BenchmarkConfig, run, add_common_args

_ROOT   = Path(__file__).parent.parent.parent.parent
_BENCH  = Path(__file__).parent

CFG = BenchmarkConfig(
    title       = "Northwind Data Discovery Benchmark",
    sql_file    = _ROOT / "data" / "northwind_sqlite.sql",
    queries_file= _ROOT / "data" / "northwind_discovery_queries.json",
    database    = "northwind",
)

DEFAULT_REPORT = str(_BENCH / "NORTHWIND_DISCOVERY_RESULTS.md")


def main() -> None:
    p = argparse.ArgumentParser(description="Northwind data discovery benchmark")
    add_common_args(p)
    args = p.parse_args()

    report = args.report
    if report == "auto":
        report = DEFAULT_REPORT

    run(
        cfg        = CFG,
        embed_model= args.embed_model,
        out_path   = args.out,
        report_path= report,
        page_size  = args.page_size,
        embed_delay= args.embed_delay,
    )


if __name__ == "__main__":
    main()
