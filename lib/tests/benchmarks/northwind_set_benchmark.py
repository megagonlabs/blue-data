"""Northwind entity-level set retrieval benchmark.

Evaluates both attribute-level Hit@K/MRR and entity-level P/R/F1.
Uses the same Northwind query file as northwind_discovery_benchmark.py,
plus a separate entity mapping file — original files are untouched.

Usage:
    python northwind_set_benchmark.py
    python northwind_set_benchmark.py --report NORTHWIND_SET_RESULTS.md
    OPENAI_API_KEY=sk-... python northwind_set_benchmark.py
"""
import argparse
from pathlib import Path

_ROOT  = Path(__file__).parent.parent.parent.parent / "data"
_BENCH = Path(__file__).parent

from _set_retrieval_runner import SetBenchmarkConfig, run, add_common_args

CFG = SetBenchmarkConfig(
    title="Northwind Set Retrieval Benchmark",
    sql_file=_ROOT / "northwind_sqlite.sql",
    queries_file=_ROOT / "northwind_discovery_queries.json",
    database="northwind",
    entity_mapping_file=_ROOT / "northwind_entity_mapping.json",
)

DEFAULT_REPORT = str(_BENCH / "NORTHWIND_SET_RESULTS.md")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    add_common_args(p)
    args = p.parse_args()

    report = args.report
    if report == "auto" or report is None:
        report = DEFAULT_REPORT

    run(
        cfg=CFG,
        embed_model=args.embed_model,
        out_path=args.out,
        report_path=report,
        page_size=args.page_size,
        embed_delay=args.embed_delay,
    )
