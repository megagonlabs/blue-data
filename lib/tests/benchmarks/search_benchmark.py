"""
Search/discovery benchmark — keyword-only vs hybrid (BM25 + embeddings).

Runs 20 queries over a DataRegistry backed by the finance SQLite dataset and
measures retrieval quality against manually curated ground truth.

Conditions:
  keyword  — BM25 only; always runs, no API key needed
  hybrid   — BM25 + OpenAI text-embedding-3-small; runs when OPENAI_API_KEY is set

Scoring per query:
  hit@1  — top result name is in the relevant set
  hit@3  — any of top-3 results is relevant
  hit@5  — any of top-5 results is relevant
  mrr    — 1/rank of first relevant result within top 10

Dataset : data/finance_sqlite.sql              (Czech banking, 5 tables)
Queries : data/search_benchmark_queries.json   (20 queries, 5 categories)

Query categories — each tests a distinct search capability:

  exact_name   (4) — query contains the exact table/attribute name
    Control questions: BM25 alone should handle these. Both conditions expected
    to score well. Validates that enrichment and embedding do not regress on
    the easy cases.

  synonym      (5) — common alternative term for the concept
    E.g. "customer" → client, "installment" → payments, "region" → district.
    BM25 struggles without a term overlap. Hybrid (semantic embeddings) should
    close the gap.

  concept      (5) — abstract intent that implies a specific column
    E.g. "running balance" → trans.balance, "loan default" → loan.status.
    Requires understanding what a column *means*, not just what it is named.
    The hardest category for keyword search.

  attribute    (4) — looking for a specific attribute within a known entity
    Tests whether attribute-level records surface above entity-level records.
    Also tests disambiguation (loan.date vs account.date).

  cross_entity (2) — intent spans multiple related entities
    E.g. "client spending history" → client + account + trans.
    Checks that relevant entity records from multiple tables all appear in top-10.

Usage:
    # keyword-only (no API key needed)
    python3 lib/tests/benchmarks/search_benchmark.py

    # keyword + hybrid (requires OPENAI_API_KEY)
    export OPENAI_API_KEY=sk-...
    python3 lib/tests/benchmarks/search_benchmark.py

    # save full results and markdown report
    python3 lib/tests/benchmarks/search_benchmark.py --out results/search.json --report
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

SQL_FILE     = Path(__file__).parent.parent.parent.parent / "data" / "finance_sqlite.sql"
QUERIES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "search_benchmark_queries.json"
DATABASE     = "finance"
DIV          = "=" * 72
DIV2         = "-" * 72
DIM          = 1536   # text-embedding-3-small dimension
K_VALUES     = [1, 3, 5]

# Open thresholds so the benchmark measures ranking quality, not filter tuning.
BENCH_CONFIG = {
    "bm25_threshold":    0.0,
    "vector_threshold":  0.0,
    "value_threshold":   0.0,
    "combined_threshold": 0.0,
    "hierarchical_enabled": False,
}


# ── Embedding ──────────────────────────────────────────────────────────────

def make_openai_embed_fn(api_key: str, model: str = "text-embedding-3-small"):
    """Returns text → list[float] using the OpenAI embeddings API."""
    import openai
    client = openai.OpenAI(api_key=api_key)

    def embed(text: str) -> list[float]:
        resp = client.embeddings.create(input=[text], model=model)
        return resp.data[0].embedding

    return embed


# ── Database ───────────────────────────────────────────────────────────────

def build_db(tmp_dir: str) -> str:
    db_path = os.path.join(tmp_dir, f"{DATABASE}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SQL_FILE.read_text())
    conn.close()
    return db_path


# ── Registry ───────────────────────────────────────────────────────────────

def build_registry(db_dir: str, embedding_fn=None) -> DataRegistry:
    source = SQLiteDBSource(
        name=DATABASE,
        properties={"connection": {"database_directory": db_dir}},
    )
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource() if embedding_fn else None,
        embedding_fn=embedding_fn,
        vector_dim=DIM if embedding_fn else None,
        rebuild=True,
        hybrid_config=BENCH_CONFIG,
    )
    reg.register_source(source)
    reg.sync_all(recursive=True)
    return reg


# ── Scoring ────────────────────────────────────────────────────────────────

def score_results(results: list[dict], relevant_names: set[str]) -> dict:
    metrics: dict[str, float] = {}
    for k in K_VALUES:
        hit = any(r.get("name") in relevant_names for r in results[:k])
        metrics[f"hit@{k}"] = 1.0 if hit else 0.0
    mrr = 0.0
    for rank, r in enumerate(results[:10], 1):
        if r.get("name") in relevant_names:
            mrr = 1.0 / rank
            break
    metrics["mrr"] = mrr
    return metrics


def topk_names(results: list[dict], k: int = 5) -> list[str]:
    return [r.get("name", "?") for r in results[:k]]


# ── Benchmark run ──────────────────────────────────────────────────────────

def run(
    embed_model: str,
    out_path: str | None,
    report_path: str | None,
    page_size: int,
    embed_delay: float,
) -> None:
    openai_key = os.environ.get("OPENAI_API_KEY")
    embedding_fn = None
    if openai_key:
        embedding_fn = make_openai_embed_fn(openai_key, embed_model)

    queries = json.loads(QUERIES_FILE.read_text())
    cats    = sorted({q["category"] for q in queries})
    n       = len(queries)

    print()
    print(DIV)
    print(f"Search / discovery benchmark   n={n} queries")
    if embedding_fn:
        print(f"Embedding model: {embed_model}   (OPENAI_API_KEY found — hybrid enabled)")
    else:
        print("No OPENAI_API_KEY — running keyword-only condition")
    print(DIV)

    tmp    = tempfile.mkdtemp(prefix="search-bench-")
    build_db(tmp)

    print("\nBuilding keyword registry (BM25 only) …")
    r_keyword = build_registry(tmp, embedding_fn=None)

    conditions: list[tuple[str, DataRegistry]] = [("keyword", r_keyword)]

    if embedding_fn:
        print(f"Building hybrid registry (BM25 + {embed_model}) …")
        r_hybrid = build_registry(tmp, embedding_fn=embedding_fn)
        conditions.append(("hybrid", r_hybrid))

    cnames = [c for c, _ in conditions]
    print(f"\nRunning {n} queries × {len(conditions)} condition(s) …\n")

    results = []
    for i, q in enumerate(queries, 1):
        relevant = set(q["relevant_names"])
        row: dict = {
            "id":            q["id"],
            "intent":        q["intent"],
            "category":      q["category"],
            "primary_name":  q["primary_name"],
            "relevant_names": q["relevant_names"],
        }

        print(f"  [{i:2}/{n}] {q['id']}  [{q['category']}]")
        print(f"         {q['intent']}")

        for cname, reg in conditions:
            search_results = reg.search_records(q["intent"], page_size=page_size)
            metrics = score_results(search_results, relevant)
            row[cname] = {
                "metrics": metrics,
                "top5":    topk_names(search_results, 5),
            }
            if embedding_fn and embed_delay > 0 and cname == "hybrid":
                time.sleep(embed_delay)

        hit_parts = "  ".join(
            f"{cn}=Hit@1={'✓' if row[cn]['metrics']['hit@1'] else '✗'}  "
            f"MRR={row[cn]['metrics']['mrr']:.2f}"
            for cn in cnames
        )
        print(f"    {hit_parts}")
        print(f"    top5(keyword)={row['keyword']['top5']}")
        if "hybrid" in cnames:
            print(f"    top5(hybrid) ={row['hybrid']['top5']}")
        print()
        results.append(row)

    # ── Summary ────────────────────────────────────────────────────────────
    print(DIV)
    print("RESULTS")
    print(DIV)

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def _metric_avg(cname: str, key: str, rows=None) -> float:
        rows = rows or results
        return avg([r[cname]["metrics"][key] for r in rows])

    print()
    col_w = 12
    metrics_labels = [
        ("Hit@1", "hit@1"),
        ("Hit@3", "hit@3"),
        ("Hit@5", "hit@5"),
        ("MRR",   "mrr"),
    ]

    header = f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames)
    print(header)
    print(DIV2)
    for label, key in metrics_labels:
        line = f"{label:<20}"
        for c in cnames:
            line += f"{_metric_avg(c, key):>{col_w}.3f}"
        print(line)

    if len(cnames) > 1:
        print()
        for key, label in [("hit@1", "Hit@1"), ("hit@3", "Hit@3"), ("hit@5", "Hit@5"), ("mrr", "MRR")]:
            b = _metric_avg("keyword", key)
            h = _metric_avg("hybrid",  key)
            delta = h - b
            sign = "+" if delta >= 0 else ""
            print(f"  Δ {label:<6} keyword → hybrid: {sign}{delta:.3f}  "
                  f"({b:.3f} → {h:.3f})")

    # ── By category ────────────────────────────────────────────────────────
    print(f"\n── By category (Hit@1) ──")
    cat_header = f"  {'Category':<16}" + "".join(f"  {c:<10}" for c in cnames) + "  n"
    print(cat_header)
    print(f"  {DIV2[:16+len(cnames)*12+4]}")
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        line = f"  {cat:<16}"
        for c in cnames:
            h1 = _metric_avg(c, "hit@1", cat_rows)
            line += f"  {h1:.0%}       "
        print(line + f"  {nc}")

    # ── Per-question detail ─────────────────────────────────────────────────
    print(f"\n── Per-question detail ──")
    hdr = f"  {'id':<12} {'category':<14}"
    for c in cnames:
        hdr += f" {'Hit@1':>5} {'MRR':>5} "
    hdr += " primary"
    print(hdr)
    print(f"  {'-'*12} {'-'*14}" + f" {'-'*5} {'-'*5}  " * len(cnames) + " " + "-"*12)
    for r in results:
        line = f"  {r['id']:<12} {r['category']:<14}"
        for c in cnames:
            h1  = "✓" if r[c]["metrics"]["hit@1"] else "✗"
            mrr = r[c]["metrics"]["mrr"]
            line += f" {h1:>5} {mrr:>5.2f} "
        print(line + f" {r['primary_name']}")

    # ── Report & save ──────────────────────────────────────────────────────
    if report_path:
        md = generate_report(results, cnames, cats, n)
        rpt = Path(report_path)
        rpt.parent.mkdir(parents=True, exist_ok=True)
        rpt.write_text(md)
        print(f"\nMarkdown report saved → {report_path}")

    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "run_at":     datetime.utcnow().isoformat() + "Z",
            "embed_model": embed_model if embedding_fn else None,
            "conditions": cnames,
            "n":          n,
            "results":    results,
        }, indent=2))
        print(f"Full results saved → {out_path}")

    print()
    print("Benchmark complete.")


# ── Report generator ───────────────────────────────────────────────────────

def generate_report(results: list, cnames: list[str], cats: list[str], n: int) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def _metric_avg(cname, key, rows=None):
        rows = rows or results
        return avg([r[cname]["metrics"][key] for r in rows])

    def _pct(v: float) -> str:
        return f"{v:.0%}"

    def _bar(v: float, width: int = 15) -> str:
        filled = round(v * width)
        return "█" * filled + "░" * (width - filled)

    lines: list[str] = []
    a = lines.append

    a("# Search / Discovery Benchmark — Results")
    a("")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in cnames)}  ")
    a(f"**Queries:** {n}  ")
    a(f"**Last run:** {now}")
    a("")
    a("> Re-generate: `python3 lib/tests/benchmarks/search_benchmark.py --report`")
    a("")
    a("---")
    a("")

    # Overall table
    a("## Overall retrieval quality")
    a("")
    header = "| Metric |" + "".join(f" {c} |" for c in cnames)
    sep    = "|--------|" + "".join("--------|" for _ in cnames)
    a(header)
    a(sep)
    for label, key in [("Hit@1", "hit@1"), ("Hit@3", "hit@3"), ("Hit@5", "hit@5"), ("MRR", "mrr")]:
        row = f"| {label} |"
        for c in cnames:
            v = _metric_avg(c, key)
            row += f" {_pct(v)} |"
        a(row)
    a("")

    # Delta table if hybrid present
    if "hybrid" in cnames:
        a("| Metric | Δ keyword → hybrid |")
        a("|--------|-------------------|")
        for label, key in [("Hit@1", "hit@1"), ("Hit@3", "hit@3"), ("Hit@5", "hit@5"), ("MRR", "mrr")]:
            b = _metric_avg("keyword", key)
            h = _metric_avg("hybrid",  key)
            delta = h - b
            sign = "+" if delta >= 0 else ""
            a(f"| {label} | **{sign}{delta:.3f}** ({_pct(b)} → {_pct(h)}) |")
        a("")

    # ASCII bars
    a("```")
    a(f"Hit@5 (% of {n} queries with a relevant result in top 5)")
    a("")
    for c in cnames:
        v = _metric_avg(c, "hit@5")
        a(f"  {c:<10}  {_bar(v)}  {_pct(v):>4}")
    a("```")
    a("")
    a("---")
    a("")

    # By category
    a("## Results by category")
    a("")

    # Mermaid chart (Hit@1 by category)
    a("```mermaid")
    a("xychart-beta")
    a('    title "Hit@1 by Category (%)"')
    short = {
        "exact_name":   "exact",
        "synonym":      "synonym",
        "concept":      "concept",
        "attribute_level": "attr",
        "cross_entity": "cross",
    }
    x_labels = [f'"{short.get(c, c)}"' for c in cats]
    a(f"    x-axis [{', '.join(x_labels)}]")
    a('    y-axis "Hit@1 (%)" 0 --> 100')
    for cname in cnames:
        vals = [round(_metric_avg(cname, "hit@1", [r for r in results if r["category"] == cat]) * 100)
                for cat in cats]
        a(f"    bar [{', '.join(str(v) for v in vals)}]")
    a("```")
    a("")
    if len(cnames) > 1:
        a("*First bar = keyword · Second bar = hybrid*")
        a("")

    # Table
    hdr = "| Category | n |"
    sep = "|---|---|"
    for c in cnames:
        hdr += f" {c} Hit@1 | {c} MRR |"
        sep += "---|---|"
    a(hdr)
    a(sep)
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        row = f"| {cat} | {nc} |"
        for c in cnames:
            h1  = _metric_avg(c, "hit@1", cat_rows)
            mrr = _metric_avg(c, "mrr",   cat_rows)
            row += f" {_pct(h1)} | {mrr:.2f} |"
        a(row)
    a("")
    a("---")
    a("")

    # Per-question
    a("## Per-question results")
    a("")
    hdr = "| ID | Category | Intent"
    sep = "|---|---|---"
    for c in cnames:
        hdr += f" | {c} Hit@1 | {c} MRR | {c} Top-3"
        sep += " |---|---|---"
    hdr += " |"
    sep += " |"
    a(hdr)
    a(sep)
    for r in results:
        intent_short = r["intent"][:50] + "…" if len(r["intent"]) > 50 else r["intent"]
        row = f"| {r['id']} | {r['category']} | {intent_short}"
        for c in cnames:
            h1  = "✅" if r[c]["metrics"]["hit@1"] else "❌"
            mrr = r[c]["metrics"]["mrr"]
            top3 = ", ".join(r[c]["top5"][:3])
            row += f" | {h1} | {mrr:.2f} | {top3}"
        row += " |"
        a(row)
    a("")
    a("---")
    a("")

    # Category descriptions
    a("## What each category tests")
    a("")
    descriptions = {
        "exact_name":
            "**Control.** Query uses the exact table or column name as it appears in the schema. "
            "BM25 term overlap should handle these reliably. Both conditions expected correct. "
            "Validates that the benchmark is not giving an unfair advantage to either condition.",
        "synonym":
            "**Term mismatch.** Common English synonym for the actual column/table name. "
            "E.g. 'customer' → client, 'installment' → payments, 'region' → district. "
            "BM25 has no term overlap and is expected to struggle. "
            "Hybrid search uses semantic embeddings to bridge the vocabulary gap.",
        "concept":
            "**Semantic intent.** Abstract concept that implies a specific column through its "
            "meaning, not its name. E.g. 'running balance' → trans.balance (STATE_VARIABLE), "
            "'repaid or defaulted' → loan.status (ENUM A/B/C/D). "
            "The hardest category for keyword search; the primary motivation for hybrid.",
        "attribute_level":
            "**Attribute precision.** Looking for a specific attribute within an entity, "
            "including disambiguation cases (loan.date vs account.date). "
            "Tests whether attribute-level records surface above entity-level records.",
        "cross_entity":
            "**Multi-table intent.** Query intent spans multiple related entities. "
            "E.g. 'client spending history' should surface client, account, and trans. "
            "Checks whether the relevant entity records from multiple tables all appear in top-10.",
    }
    for cat in sorted(cats):
        a(f"### {cat}")
        a("")
        a(descriptions.get(cat, ""))
        a("")

    return "\n".join(lines)


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Search/discovery benchmark")
    p.add_argument(
        "--embed-model", default="text-embedding-3-small",
        help="OpenAI embedding model (default: text-embedding-3-small). "
             "Ignored when OPENAI_API_KEY is not set.",
    )
    p.add_argument(
        "--out", default=None,
        help="Save detailed JSON results to this path",
    )
    p.add_argument(
        "--report", default=None, const="lib/tests/benchmarks/SEARCH_RESULTS.md",
        nargs="?",
        help="Write markdown report (default path: lib/tests/benchmarks/SEARCH_RESULTS.md)",
    )
    p.add_argument(
        "--page-size", type=int, default=10,
        help="Number of search results to retrieve per query (default: 10)",
    )
    p.add_argument(
        "--embed-delay", type=float, default=0.1,
        help="Seconds to sleep between embedding API calls to avoid rate limits (default: 0.1)",
    )
    args = p.parse_args()
    run(
        embed_model=args.embed_model,
        out_path=args.out,
        report_path=args.report,
        page_size=args.page_size,
        embed_delay=args.embed_delay,
    )


if __name__ == "__main__":
    main()
