"""
Shared engine for data discovery benchmarks.

Each benchmark script supplies a BenchmarkConfig and calls run().

Conditions (up to 4, depending on env vars set):
  keyword          — BM25 only, no enrichment          (always runs)
  keyword_enriched — BM25 only, Layer-1 enrichment     (always runs)
  hybrid           — BM25 + embeddings, no enrichment  (requires OPENAI_API_KEY)
  hybrid_enriched  — BM25 + embeddings, enrichment     (requires OPENAI_API_KEY)

Enrichment = Layer 1 SemanticTypeInferencer (deterministic, no API key needed).
It annotates attribute records with semantic_type and sample value examples,
which are then indexed — improving retrieval for enum-coded and opaque columns.

Query JSON format
-----------------
Each query object must have:
  id, intent, category, primary_name, relevant_names

Optional:
  enrichment_sensitive  bool  — true when enrichment is expected to help
                                (opaque column names, coded enum values, etc.)
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


def _collect_stats(reg: DataRegistry, source_name: str) -> None:
    """Collect attribute-level stats so SemanticTypeInferencer has sample values."""
    for db_rec in reg.list_source_databases(source_name):
        db = db_rec["name"]
        for coll_rec in reg.list_database_collections(source_name, db):
            coll = coll_rec["name"]
            for entity_rec in reg.list_collection_entities(source_name, db, coll):
                entity = entity_rec["name"]
                for attr_rec in reg.list_entity_attributes(source_name, db, coll, entity):
                    attr = attr_rec["name"]
                    reg.collect_source_database_collection_entity_attribute_stats(
                        source_name, db, coll, entity, attr
                    )


def build_registry(
    db_dir: str,
    database: str,
    embedding_fn=None,
    enrich: bool = False,
) -> DataRegistry:
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

    if enrich:
        _collect_stats(reg, database)
        reg.enrich_source(database)

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
    n_sens  = sum(1 for q in queries if q.get("enrichment_sensitive", False))

    print()
    print(DIV)
    print(f"{cfg.title}   n={n} queries ({n_sens} enrichment-sensitive)")
    if embedding_fn:
        print(f"Embedding model: {embed_model}   (OPENAI_API_KEY found — hybrid enabled)")
    else:
        print("No OPENAI_API_KEY — running keyword conditions only")
    print(DIV)

    tmp = tempfile.mkdtemp(prefix="disc-bench-")
    build_db(tmp, cfg.sql_file, cfg.database)

    print(f"\nBuilding keyword registry (no enrichment) …")
    r_kw = build_registry(tmp, cfg.database, embedding_fn=None, enrich=False)

    print(f"Building keyword_enriched registry (Layer-1 enrichment) …")
    r_kw_enr = build_registry(tmp, cfg.database, embedding_fn=None, enrich=True)

    conditions: list[tuple[str, DataRegistry]] = [
        ("keyword",          r_kw),
        ("keyword_enriched", r_kw_enr),
    ]

    if embedding_fn:
        print(f"Building hybrid registry (BM25 + {embed_model}, no enrichment) …")
        r_hyb = build_registry(tmp, cfg.database, embedding_fn=embedding_fn, enrich=False)
        print(f"Building hybrid_enriched registry (BM25 + {embed_model} + enrichment) …")
        r_hyb_enr = build_registry(tmp, cfg.database, embedding_fn=embedding_fn, enrich=True)
        conditions += [
            ("hybrid",          r_hyb),
            ("hybrid_enriched", r_hyb_enr),
        ]

    cnames = [c for c, _ in conditions]
    print(f"\nRunning {n} queries × {len(conditions)} condition(s) …\n")

    results = []
    for i, q in enumerate(queries, 1):
        relevant  = set(q["relevant_names"])
        sensitive = q.get("enrichment_sensitive", False)
        row: dict = {
            "id":                   q["id"],
            "intent":               q["intent"],
            "category":             q["category"],
            "primary_name":         q["primary_name"],
            "relevant_names":       q["relevant_names"],
            "enrichment_sensitive": sensitive,
        }

        sens_mark = " ★" if sensitive else ""
        print(f"  [{i:2}/{n}] {q['id']}  [{q['category']}]{sens_mark}")
        print(f"         {q['intent']}")

        for cname, reg in conditions:
            search_results = reg.search_records(q["intent"], page_size=page_size)
            metrics = score_results(search_results, relevant)
            row[cname] = {"metrics": metrics, "top5": topk_names(search_results, 5)}
            if embedding_fn and embed_delay > 0 and cname in ("hybrid", "hybrid_enriched"):
                time.sleep(embed_delay)

        hit_parts = "  ".join(
            f"{cn}={'✓' if row[cn]['metrics']['hit@1'] else '✗'}"
            for cn in cnames
        )
        print(f"    Hit@1: {hit_parts}")
        print(f"    top5({cnames[0]})={row[cnames[0]]['top5']}")
        if len(cnames) > 1:
            print(f"    top5({cnames[1]})={row[cnames[1]]['top5']}")
        print()
        results.append(row)

    # ── Summary ────────────────────────────────────────────────────────────
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    def _ma(cname, key, rows=None):
        rows = rows or results
        return avg([r[cname]["metrics"][key] for r in rows if cname in r])

    print(DIV)
    print("RESULTS — all questions")
    print(DIV)
    col_w = 18
    header = f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames)
    print(header)
    print(DIV2)
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        line = f"{label:<20}"
        for c in cnames:
            line += f"{_ma(c, key):>{col_w}.3f}"
        print(line)

    sens_rows = [r for r in results if r.get("enrichment_sensitive")]
    if sens_rows:
        print()
        print(f"── Enrichment-sensitive questions only ({len(sens_rows)}) ──")
        header2 = f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames)
        print(header2)
        print(DIV2)
        for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
            line = f"{label:<20}"
            for c in cnames:
                line += f"{_ma(c, key, sens_rows):>{col_w}.3f}"
            print(line)

    print(f"\n── By category (Hit@1) ──")
    cat_header = f"  {'Category':<20}" + "".join(f"  {c:<18}" for c in cnames) + "  n"
    print(cat_header)
    print(f"  {'-'*80}")
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        line = f"  {cat:<20}"
        for c in cnames:
            line += f"  {_ma(c, 'hit@1', cat_rows):<18.0%}"
        print(line + f"  {nc}")

    print(f"\n── Per-question detail ──")
    hdr = f"  {'id':<16} {'cat':<22} {'sens':>4}"
    for c in cnames:
        hdr += f" {'H@1':>4} {'MRR':>5}"
    hdr += "  primary"
    print(hdr)
    print(f"  {'-'*16} {'-'*22} {'-'*4}" + f" {'-'*4} {'-'*5}" * len(cnames) + "  " + "-"*14)
    for r in results:
        sens = "★" if r.get("enrichment_sensitive") else ""
        line = f"  {r['id']:<16} {r['category']:<22} {sens:>4}"
        for c in cnames:
            h1  = "✓" if r[c]["metrics"]["hit@1"] else "✗"
            mrr = r[c]["metrics"]["mrr"]
            line += f" {h1:>4} {mrr:>5.2f}"
        print(line + f"  {r['primary_name']}")

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
        return avg([r[cname]["metrics"][key] for r in rows if cname in r])
    def _pct(v): return f"{v:.0%}"
    def _bar(v, width=15):
        filled = round(v * width)
        return "█" * filled + "░" * (width - filled)

    lines: list[str] = []
    a = lines.append

    sens_rows = [r for r in results if r.get("enrichment_sensitive")]

    a(f"# {title} — Results")
    a("")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in cnames)}  ")
    a(f"**Queries:** {n} total, {len(sens_rows)} enrichment-sensitive  ")
    a(f"**Last run:** {now}")
    a("")
    a("> Enrichment = Layer-1 SemanticTypeInferencer (deterministic, no API key).")
    a("> ★ marks queries where opaque column names or coded enum values make enrichment helpful.")
    a("")
    a("---")
    a("")

    # Overall table
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

    # Delta table — keyword as baseline
    a("| Metric | Δ kw → kw_enr | Δ kw → hybrid | Δ kw → hyb_enr |")
    a("|--------|---------------|---------------|----------------|")
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        base = _ma("keyword", key)
        d_kwe  = _ma("keyword_enriched", key) - base if "keyword_enriched" in cnames else None
        d_hyb  = _ma("hybrid", key) - base if "hybrid" in cnames else None
        d_hybe = _ma("hybrid_enriched", key) - base if "hybrid_enriched" in cnames else None

        def _fmt(d):
            if d is None: return " n/a"
            sign = "+" if d >= 0 else ""
            return f"**{sign}{d:.3f}**"

        a(f"| {label} | {_fmt(d_kwe)} | {_fmt(d_hyb)} | {_fmt(d_hybe)} |")
    a("")

    # ASCII bars
    a("```")
    a(f"Hit@5 (% of {n} queries with a relevant result in top 5)")
    a("")
    for c in cnames:
        v = _ma(c, "hit@5")
        a(f"  {c:<20}  {_bar(v)}  {_pct(v):>4}")
    a("```")
    a("")
    a("---")
    a("")

    # Enrichment-sensitive subset
    if sens_rows:
        a("## Enrichment-sensitive questions")
        a("")
        a(f"These {len(sens_rows)} questions target opaque column names or coded enum values "
          "where enrichment annotations are expected to improve retrieval.")
        a("")
        header2 = "| Metric |" + "".join(f" {c} |" for c in cnames)
        sep2    = "|--------|" + "".join("---------|" for _ in cnames)
        a(header2); a(sep2)
        for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
            row = f"| {label} |"
            for c in cnames:
                row += f" {_pct(_ma(c, key, sens_rows))} |"
            a(row)
        a("")
        a("---")
        a("")

    # By category
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
        a("*Bars left-to-right: " + " · ".join(cnames) + "*")
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

    # Per-question
    a("## Per-question results")
    a("")
    hdr = "| ID | Cat | ★ | Intent"
    sep = "|---|---|---|---"
    for c in cnames:
        hdr += f" | {c} H@1 | {c} MRR | {c} Top-3"
        sep += " |---|---|---"
    hdr += " |"; sep += " |"
    a(hdr); a(sep)
    for r in results:
        intent_short = r["intent"][:50] + "…" if len(r["intent"]) > 50 else r["intent"]
        sens = "★" if r.get("enrichment_sensitive") else ""
        row = f"| {r['id']} | {r['category']} | {sens} | {intent_short}"
        for c in cnames:
            if c not in r:
                row += " | — | — | —"
                continue
            h1   = "✅" if r[c]["metrics"]["hit@1"] else "❌"
            mrr  = r[c]["metrics"]["mrr"]
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
