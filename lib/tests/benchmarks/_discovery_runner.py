"""
Shared engine for data discovery benchmarks.

Each benchmark script supplies a BenchmarkConfig and calls run().
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

DIM      = 1536   # text-embedding-3-small
K_VALUES = [1, 3, 5]
DIV      = "=" * 72
DIV2     = "-" * 72

BENCH_CONFIG = {
    "bm25_threshold":     0.0,
    "vector_threshold":   0.0,
    "value_threshold":    0.0,
    "combined_threshold": 0.0,
    "hierarchical_enabled": False,
}


@dataclass
class BenchmarkConfig:
    title: str          # shown in header and report
    sql_file: Path      # path to .sql schema+data file
    queries_file: Path  # path to JSON query dataset
    database: str       # database name used in SQLiteDBSource


# ── Embedding ──────────────────────────────────────────────────────────────

def make_openai_embed_fn(api_key: str, model: str = "text-embedding-3-small"):
    import openai
    client = openai.OpenAI(api_key=api_key)

    def embed(text: str) -> list[float]:
        resp = client.embeddings.create(input=[text], model=model)
        return resp.data[0].embedding

    return embed


# ── Database + registry ────────────────────────────────────────────────────

def build_db(tmp_dir: str, sql_file: Path, database: str) -> str:
    db_path = os.path.join(tmp_dir, f"{database}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(sql_file.read_text())
    conn.close()
    return db_path


def build_registry(db_dir: str, database: str, embedding_fn=None) -> DataRegistry:
    source = SQLiteDBSource(
        name=database,
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


# ── Main run ───────────────────────────────────────────────────────────────

def run(
    cfg: BenchmarkConfig,
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

    queries = json.loads(cfg.queries_file.read_text())
    cats    = sorted({q["category"] for q in queries})
    n       = len(queries)

    print()
    print(DIV)
    print(f"{cfg.title}   n={n} queries")
    if embedding_fn:
        print(f"Embedding model: {embed_model}   (OPENAI_API_KEY found — hybrid enabled)")
    else:
        print("No OPENAI_API_KEY — running keyword-only condition")
    print(DIV)

    tmp = tempfile.mkdtemp(prefix="disc-bench-")
    build_db(tmp, cfg.sql_file, cfg.database)

    print(f"\nBuilding keyword registry (BM25 only) …")
    r_keyword = build_registry(tmp, cfg.database, embedding_fn=None)

    conditions: list[tuple[str, DataRegistry]] = [("keyword", r_keyword)]

    if embedding_fn:
        print(f"Building hybrid registry (BM25 + {embed_model}) …")
        r_hybrid = build_registry(tmp, cfg.database, embedding_fn=embedding_fn)
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

    def avg(lst): return sum(lst) / len(lst) if lst else 0.0

    def _ma(cname, key, rows=None):
        rows = rows or results
        return avg([r[cname]["metrics"][key] for r in rows])

    print()
    col_w = 12
    header = f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames)
    print(header)
    print(DIV2)
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        line = f"{label:<20}"
        for c in cnames:
            line += f"{_ma(c, key):>{col_w}.3f}"
        print(line)

    if len(cnames) > 1:
        print()
        for key, label in [("hit@1","Hit@1"),("hit@3","Hit@3"),("hit@5","Hit@5"),("mrr","MRR")]:
            b = _ma("keyword", key); h = _ma("hybrid", key)
            sign = "+" if h >= b else ""
            print(f"  Δ {label:<6} keyword → hybrid: {sign}{h-b:.3f}  ({b:.3f} → {h:.3f})")

    print(f"\n── By category (Hit@1) ──")
    cat_header = f"  {'Category':<16}" + "".join(f"  {c:<10}" for c in cnames) + "  n"
    print(cat_header)
    print(f"  {'-'*60}")
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        line = f"  {cat:<16}"
        for c in cnames:
            line += f"  {_ma(c, 'hit@1', cat_rows):.0%}       "
        print(line + f"  {nc}")

    print(f"\n── Per-question detail ──")
    hdr = f"  {'id':<14} {'category':<14}"
    for c in cnames:
        hdr += f" {'H@1':>4} {'MRR':>5} "
    hdr += " primary"
    print(hdr)
    print(f"  {'-'*14} {'-'*14}" + f" {'-'*4} {'-'*5}  " * len(cnames) + " " + "-"*12)
    for r in results:
        line = f"  {r['id']:<14} {r['category']:<14}"
        for c in cnames:
            h1  = "✓" if r[c]["metrics"]["hit@1"] else "✗"
            mrr = r[c]["metrics"]["mrr"]
            line += f" {h1:>4} {mrr:>5.2f} "
        print(line + f" {r['primary_name']}")

    if report_path:
        md = generate_report(cfg.title, results, cnames, cats, n)
        rpt = Path(report_path)
        rpt.parent.mkdir(parents=True, exist_ok=True)
        rpt.write_text(md)
        print(f"\nMarkdown report saved → {report_path}")

    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "run_at":      datetime.utcnow().isoformat() + "Z",
            "title":       cfg.title,
            "embed_model": embed_model if embedding_fn else None,
            "conditions":  cnames,
            "n":           n,
            "results":     results,
        }, indent=2))
        print(f"Full results saved → {out_path}")

    print()
    print("Benchmark complete.")


# ── Report ─────────────────────────────────────────────────────────────────

def generate_report(title: str, results: list, cnames: list[str],
                    cats: list[str], n: int) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    def _ma(cname, key, rows=None):
        rows = rows or results
        return avg([r[cname]["metrics"][key] for r in rows])
    def _pct(v): return f"{v:.0%}"
    def _bar(v, width=15):
        filled = round(v * width)
        return "█" * filled + "░" * (width - filled)

    lines: list[str] = []
    a = lines.append

    a(f"# {title} — Results")
    a("")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in cnames)}  ")
    a(f"**Queries:** {n} analytical discovery questions  ")
    a(f"**Last run:** {now}")
    a("")
    a("---")
    a("")

    a("## Overall retrieval quality")
    a("")
    header = "| Metric |" + "".join(f" {c} |" for c in cnames)
    sep    = "|--------|" + "".join("---------|" for _ in cnames)
    a(header); a(sep)
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        row = f"| {label} |"
        for c in cnames:
            row += f" {_pct(_ma(c, key))} |"
        a(row)
    a("")

    if "hybrid" in cnames:
        a("| Metric | Δ keyword → hybrid |")
        a("|--------|--------------------|")
        for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
            b = _ma("keyword", key); h = _ma("hybrid", key)
            sign = "+" if h >= b else ""
            a(f"| {label} | **{sign}{h-b:.3f}** ({_pct(b)} → {_pct(h)}) |")
        a("")

    a("```")
    a(f"Hit@5 (% of {n} questions with a relevant result in top 5)")
    a("")
    for c in cnames:
        v = _ma(c, "hit@5")
        a(f"  {c:<10}  {_bar(v)}  {_pct(v):>4}")
    a("```")
    a("")
    a("---")
    a("")

    a("## Results by category")
    a("")
    a("```mermaid")
    a("xychart-beta")
    a(f'    title "Hit@1 by Category (%)"')
    x_labels = [f'"{c}"' for c in cats]
    a(f"    x-axis [{', '.join(x_labels)}]")
    a('    y-axis "Hit@1 (%)" 0 --> 100')
    for cname in cnames:
        vals = [round(_ma(cname, "hit@1", [r for r in results if r["category"] == cat]) * 100)
                for cat in cats]
        a(f"    bar [{', '.join(str(v) for v in vals)}]")
    a("```")
    a("")
    if len(cnames) > 1:
        a("*First bar = keyword · Second bar = hybrid*")
        a("")

    hdr = "| Category | n |"
    sep = "|---|---|"
    for c in cnames:
        hdr += f" {c} Hit@1 | {c} MRR |"; sep += "---|---|"
    a(hdr); a(sep)
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        row = f"| {cat} | {nc} |"
        for c in cnames:
            row += f" {_pct(_ma(c, 'hit@1', cat_rows))} | {_ma(c, 'mrr', cat_rows):.2f} |"
        a(row)
    a("")
    a("---")
    a("")

    a("## Per-question results")
    a("")
    hdr = "| ID | Category | Intent"
    sep = "|---|---|---"
    for c in cnames:
        hdr += f" | {c} H@1 | {c} MRR | {c} Top-3"
        sep += " |---|---|---"
    hdr += " |"; sep += " |"
    a(hdr); a(sep)
    for r in results:
        intent_short = r["intent"][:55] + "…" if len(r["intent"]) > 55 else r["intent"]
        row = f"| {r['id']} | {r['category']} | {intent_short}"
        for c in cnames:
            h1  = "✅" if r[c]["metrics"]["hit@1"] else "❌"
            mrr = r[c]["metrics"]["mrr"]
            top3 = ", ".join(r[c]["top5"][:3])
            row += f" | {h1} | {mrr:.2f} | {top3}"
        row += " |"
        a(row)
    a("")

    return "\n".join(lines)


# ── CLI helpers ────────────────────────────────────────────────────────────

def add_common_args(p):
    """Add shared CLI arguments to an argparse parser."""
    p.add_argument("--embed-model", default="text-embedding-3-small",
                   help="OpenAI embedding model (default: text-embedding-3-small)")
    p.add_argument("--out", default=None,
                   help="Save detailed JSON results to this path")
    p.add_argument("--report", default=None, nargs="?", const="auto",
                   help="Write markdown report (pass path or omit for default)")
    p.add_argument("--page-size", type=int, default=10,
                   help="Search results to retrieve per query (default: 10)")
    p.add_argument("--embed-delay", type=float, default=0.1,
                   help="Seconds between embedding API calls (default: 0.1)")
    return p
