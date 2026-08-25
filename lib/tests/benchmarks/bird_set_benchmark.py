"""BIRD set retrieval benchmark — all 11 dev databases.

Runs entity-level P/R/F1 + attribute-level Hit@K/MRR on the full BIRD dev set
(1534 questions across 11 SQLite databases).

Usage:
    python bird_set_benchmark.py
    python bird_set_benchmark.py --db financial           # single database
    python bird_set_benchmark.py --report auto
    OPENAI_API_KEY=sk-... python bird_set_benchmark.py   # hybrid condition too
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_BENCH    = Path(__file__).parent
_DATA     = Path(__file__).parent.parent.parent.parent / "data" / "bird"

sys.path.insert(0, str(_BENCH))
from _set_retrieval_runner import (
    SetBenchmarkConfig,
    add_common_args,
    build_registry,
    score_attribute,
    score_entity_set,
    score_entity_ideal,
    topk_names,
    generate_report,
    make_openai_embed_fn,
    K_VALUES,
    ENTITY_K_VALUES,
    DIM,
    DIV,
    DIV2,
)

DATABASES = [
    "california_schools",
    "card_games",
    "codebase_community",
    "debit_card_specializing",
    "european_football_2",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]


def run_bird(
    databases: list[str],
    embed_model: str,
    report_dir: Path | None,
    page_size: int,
    embed_delay: float,
) -> None:
    openai_key = os.environ.get("OPENAI_API_KEY")
    embedding_fn = None
    if openai_key:
        embedding_fn = make_openai_embed_fn(openai_key, embed_model)

    conditions = ["keyword"] + (["hybrid"] if embedding_fn else [])
    all_results: dict[str, list[dict]] = {c: [] for c in conditions}
    db_summaries: list[dict] = []

    for db in databases:
        sqlite_path = _DATA / f"{db}.sqlite"
        queries_file = _DATA / f"{db}_discovery_queries.json"
        em_file      = _DATA / f"{db}_entity_mapping.json"

        if not sqlite_path.exists():
            print(f"  SKIP {db}: SQLite not found at {sqlite_path}")
            continue
        if not queries_file.exists():
            print(f"  SKIP {db}: query file not found")
            continue

        queries      = json.loads(queries_file.read_text())
        entity_map   = json.loads(em_file.read_text()) if em_file.exists() else {}
        n            = len(queries)

        print(f"\n{DIV}")
        print(f"{db}   ({n} queries)")
        print(DIV)

        tmp = tempfile.mkdtemp(prefix=f"bird-{db}-")
        shutil.copy(sqlite_path, os.path.join(tmp, f"{db}.db"))

        registries: dict[str, object] = {}
        print(f"  Building keyword registry …")
        registries["keyword"] = build_registry(tmp, db, embedding_fn=None)
        if embedding_fn:
            print(f"  Building hybrid registry …")
            registries["hybrid"] = build_registry(tmp, db, embedding_fn=embedding_fn)

        db_rows: list[dict] = []
        for i, q in enumerate(queries, 1):
            relevant_names    = set(q.get("relevant_names", []))
            relevant_entities = set(entity_map.get(q["id"], []))

            row: dict = {
                "id":               q["id"],
                "intent":           q["intent"],
                "category":         q["category"],
                "primary_name":     q.get("primary_name", ""),
                "relevant_names":   q.get("relevant_names", []),
                "relevant_entities": list(relevant_entities),
                "db":               db,
            }

            for cname, reg in registries.items():
                sr      = reg.search_records(q["intent"], page_size=page_size)
                attr_m  = score_attribute(sr, relevant_names)
                entity_m = {}
                if relevant_entities:
                    for k in ENTITY_K_VALUES:
                        em = score_entity_set(sr, relevant_entities, k)
                        entity_m[f"p@{k}"]  = em["precision"]
                        entity_m[f"r@{k}"]  = em["recall"]
                        entity_m[f"f1@{k}"] = em["f1"]
                    ideal = score_entity_ideal(sr, relevant_entities)
                    entity_m["p@ideal"]  = ideal["precision"]
                    entity_m["r@ideal"]  = ideal["recall"]
                    entity_m["f1@ideal"] = ideal["f1"]
                row[cname] = {
                    "attr_metrics":   attr_m,
                    "entity_metrics": entity_m,
                    "top5":           topk_names(sr, 5),
                }

            db_rows.append(row)
            for c in conditions:
                all_results[c].append(row)

        def avg(lst): return sum(lst) / len(lst) if lst else 0.0
        def _a(c, k): return avg([r[c]["attr_metrics"][k] for r in db_rows])
        def _e(c, k):
            vals = [r[c]["entity_metrics"].get(k) for r in db_rows
                    if r[c]["entity_metrics"]]
            return avg([v for v in vals if v is not None])

        summary = {}
        for c in conditions:
            summary[c] = {
                "hit@1": _a(c, "hit@1"), "hit@5": _a(c, "hit@5"),
                "mrr":   _a(c, "mrr"),
                "f1@ideal": _e(c, "f1@ideal"),
            }
        db_summaries.append({"db": db, "n": n, **summary})

        line = f"  n={n}"
        for c in conditions:
            s = summary[c]
            line += (f"  [{c}] H@1={s['hit@1']:.0%}  H@5={s['hit@5']:.0%}"
                     f"  MRR={s['mrr']:.2f}  F1@Ideal={s['f1@ideal']:.2f}")
        print(line)

        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            cats = sorted({r["category"] for r in db_rows})
            md = generate_report(
                f"BIRD — {db}", db_rows, conditions, cats, n, bool(entity_map)
            )
            rp = report_dir / f"BIRD_{db.upper()}_RESULTS.md"
            rp.write_text(md)

        shutil.rmtree(tmp, ignore_errors=True)

    _print_combined(db_summaries, conditions, all_results)

    if report_dir:
        _write_combined_report(db_summaries, conditions, all_results, report_dir)


def _print_combined(summaries, conditions, all_results):
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0

    total = sum(s["n"] for s in summaries)
    print(f"\n{DIV}")
    print(f"BIRD COMBINED   {total} queries   {len(summaries)} databases")
    print(DIV)
    print(f"\n{'DB':<30}" + "".join(
        f"  {c} H@1   H@5   MRR  F1@I" for c in conditions))
    print(DIV2)
    for s in summaries:
        line = f"{s['db']:<30}"
        for c in conditions:
            if c in s:
                line += (f"  {s[c]['hit@1']:>4.0%}  {s[c]['hit@5']:>4.0%}"
                         f"  {s[c]['mrr']:.2f}  {s[c]['f1@ideal']:.2f}")
        print(line)
    print(DIV2)
    line = f"{'OVERALL':<30}"
    for c in conditions:
        rows = all_results[c]
        def _a(k): return avg([r[c]["attr_metrics"][k] for r in rows])
        def _e(k):
            vals = [r[c]["entity_metrics"].get(k) for r in rows
                    if r[c]["entity_metrics"]]
            return avg([v for v in vals if v is not None])
        line += (f"  {_a('hit@1'):>4.0%}  {_a('hit@5'):>4.0%}"
                 f"  {_a('mrr'):.2f}  {_e('f1@ideal'):.2f}")
    print(line)


def _write_combined_report(summaries, conditions, all_results, report_dir):
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    now  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(s["n"] for s in summaries)

    lines = []
    a = lines.append
    a("# BIRD Set Retrieval Benchmark — Combined Results")
    a("")
    a(f"**Dataset:** BIRD dev set ({total} questions, {len(summaries)} databases)  ")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in conditions)}  ")
    a(f"**Last run:** {now}")
    a("")
    a("> Metrics: attribute-level Hit@K/MRR + entity-level P/R/F1@Ideal-K.")
    a("> Ideal-K uses exactly |relevant tables| as the cutoff.")
    a("")
    a("---")
    a("")
    a("## Per-database summary")
    a("")
    hdr = "| Database | n |"
    sep = "|---|---|"
    for c in conditions:
        hdr += f" {c} Hit@1 | {c} Hit@5 | {c} MRR | {c} F1@Ideal-K |"
        sep  += "---|---|---|---|"
    a(hdr); a(sep)
    for s in summaries:
        row = f"| {s['db']} | {s['n']} |"
        for c in conditions:
            if c in s:
                row += (f" {s[c]['hit@1']:.0%} | {s[c]['hit@5']:.0%}"
                        f" | {s[c]['mrr']:.2f} | {s[c]['f1@ideal']:.2f} |")
        a(row)

    a("| **OVERALL** | **" + str(total) + "** |")
    for c in conditions:
        rows = all_results[c]
        def _a(k): return avg([r[c]["attr_metrics"][k] for r in rows])
        def _e(k):
            vals = [r[c]["entity_metrics"].get(k) for r in rows
                    if r[c]["entity_metrics"]]
            return avg([v for v in vals if v is not None])
    a("")

    rp = report_dir / "BIRD_COMBINED_RESULTS.md"
    rp.write_text("\n".join(lines))
    print(f"\nCombined report → {rp}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=None,
                   help="Run only this database (default: all)")
    p.add_argument("--report-dir", default=None,
                   help="Directory to write per-db and combined markdown reports")
    add_common_args(p)
    args = p.parse_args()

    dbs = [args.db] if args.db else DATABASES
    report_dir = Path(args.report_dir) if args.report_dir else None

    run_bird(
        databases=dbs,
        embed_model=args.embed_model,
        report_dir=report_dir,
        page_size=args.page_size,
        embed_delay=args.embed_delay,
    )
