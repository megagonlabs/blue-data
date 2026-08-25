"""
Finance data discovery benchmark.

Tests whether search_records surfaces the correct entities and attributes
to answer real analytical questions about the Czech banking dataset.

Conditions:
  keyword  — BM25 only; always runs, no API key needed
  hybrid   — BM25 + OpenAI text-embedding-3-small; runs when OPENAI_API_KEY is set

Scoring: Hit@1, Hit@3, Hit@5, MRR against manually curated ground truth.

Dataset : data/finance_sqlite.sql    (district, client, account, loan, trans)
Queries : data/finance_discovery_queries.json  (40 analytical questions)

Query categories:
  aggregation (6) — counting, summing, averaging over a single entity
  filter      (6) — finding records matching a coded or threshold condition
  join        (9) — intent spans multiple entities via foreign keys
  temporal    (5) — date-based grouping or ordering
  concept     (7) — abstract intent that maps to a non-obvious column
                    (e.g. "current balance" → trans.balance STATE_VARIABLE)
  schema      (3) — what data/entities exist for a given concept
  attribute   (4) — which specific column stores a named piece of information

Usage:
    # keyword-only (no API key needed)
    python3 lib/tests/benchmarks/finance_discovery_benchmark.py

    # keyword + hybrid
    export OPENAI_API_KEY=sk-...
    python3 lib/tests/benchmarks/finance_discovery_benchmark.py

    # save results and report
    python3 lib/tests/benchmarks/finance_discovery_benchmark.py \\
        --out results/finance_discovery.json --report
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _discovery_runner import BenchmarkConfig, run, add_common_args

_ROOT   = Path(__file__).parent.parent.parent.parent
_BENCH  = Path(__file__).parent

CFG = BenchmarkConfig(
    title       = "Finance Data Discovery Benchmark",
    sql_file    = _ROOT / "data" / "finance_sqlite.sql",
    queries_file= _ROOT / "data" / "finance_discovery_queries.json",
    database    = "finance",
)

DEFAULT_REPORT = str(_BENCH / "FINANCE_DISCOVERY_RESULTS.md")


def main() -> None:
    p = argparse.ArgumentParser(description="Finance data discovery benchmark")
    add_common_args(p)
    args = p.parse_args()

    report = args.report
    if report is None or report == "auto":
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
