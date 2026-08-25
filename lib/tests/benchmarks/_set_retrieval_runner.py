"""
Set-retrieval benchmark runner.

Evaluates two complementary metrics:
  - Attribute-level  Hit@K / MRR  (any relevant name in top-K — same as _discovery_runner)
  - Entity-level     P/R/F1@K     (set overlap between retrieved entity records and
                                   expected entity set — comparable to MEW / CORE-T)

Each benchmark script supplies a SetBenchmarkConfig and calls run().
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

DIM      = 1536
K_VALUES = [1, 3, 5]
ENTITY_K_VALUES = [3, 5, 10]   # entity-set P/R/F1 at these Ks
DIV  = "=" * 72
DIV2 = "-" * 72

BENCH_CONFIG = {
    "bm25_threshold":     0.0,
    "vector_threshold":   0.0,
    "value_threshold":    0.0,
    "combined_threshold": 0.0,
    "hierarchical_enabled": False,
}


@dataclass
class SetBenchmarkConfig:
    title: str
    sql_file: Path
    queries_file: Path
    database: str
    entity_mapping_file: Path | None = None   # optional: query_id -> [entity names]


# ── Embedding ──────────────────────────────────────────────────────────────

def make_openai_embed_fn(api_key: str, model: str = "text-embedding-3-small"):
    import openai
    client = openai.OpenAI(api_key=api_key)
    def embed(text: str) -> list[float]:
        resp = client.embeddings.create(input=[text], model=model)
        return resp.data[0].embedding
    return embed


# ── Registry ───────────────────────────────────────────────────────────────

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


# ── Attribute-level scoring (Hit@K / MRR) ─────────────────────────────────

def score_attribute(results: list[dict], relevant_names: set[str]) -> dict:
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


# ── Entity-level scoring (P / R / F1 @ K) ─────────────────────────────────

def score_entity_set(results: list[dict], relevant_entities: set[str], k: int) -> dict:
    entity_results = [r for r in results[:k] if r.get("type") == "entity"]
    retrieved = {r.get("name") for r in entity_results if r.get("name")}

    if not relevant_entities:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = len(retrieved & relevant_entities)
    precision = tp / len(retrieved) if retrieved else 0.0
    recall    = tp / len(relevant_entities)
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1}


def score_entity_ideal(results: list[dict], relevant_entities: set[str]) -> dict:
    """Ideal-K: use exactly |relevant_entities| as the cutoff."""
    k = max(1, len(relevant_entities))
    return score_entity_set(results, relevant_entities, k)


def topk_names(results: list[dict], k: int = 5) -> list[str]:
    return [r.get("name", "?") for r in results[:k]]


# ── Main run ───────────────────────────────────────────────────────────────

def run(
    cfg: SetBenchmarkConfig,
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
    entity_mapping: dict[str, list[str]] = {}
    if cfg.entity_mapping_file and cfg.entity_mapping_file.exists():
        entity_mapping = json.loads(cfg.entity_mapping_file.read_text())

    has_entity = bool(entity_mapping)
    cats = sorted({q["category"] for q in queries})
    n    = len(queries)

    print()
    print(DIV)
    print(f"{cfg.title}   n={n} queries")
    if embedding_fn:
        print(f"Embedding model: {embed_model}   (OPENAI_API_KEY found — hybrid enabled)")
    else:
        print("No OPENAI_API_KEY — running keyword-only condition")
    if has_entity:
        print("Entity mapping loaded — entity-level P/R/F1 will be computed")
    print(DIV)

    tmp = tempfile.mkdtemp(prefix="set-bench-")
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
        relevant_names    = set(q.get("relevant_names", []))
        relevant_entities = set(entity_mapping.get(q["id"], []))

        row: dict = {
            "id":               q["id"],
            "intent":           q["intent"],
            "category":         q["category"],
            "primary_name":     q.get("primary_name", ""),
            "relevant_names":   q.get("relevant_names", []),
            "relevant_entities": list(relevant_entities),
        }

        print(f"  [{i:2}/{n}] {q['id']}  [{q['category']}]")
        print(f"         {q['intent']}")

        for cname, reg in conditions:
            sr = reg.search_records(q["intent"], page_size=page_size)
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
                "top10_entities": topk_names(
                    [r for r in sr if r.get("type") == "entity"], 10
                ),
            }
            if embedding_fn and embed_delay > 0 and cname == "hybrid":
                time.sleep(embed_delay)

        summary = "  ".join(
            f"{cn}: H@1={'✓' if row[cn]['attr_metrics']['hit@1'] else '✗'}"
            + (f"  F1@ideal={row[cn]['entity_metrics'].get('f1@ideal', 0):.2f}"
               if relevant_entities else "")
            for cn in cnames
        )
        print(f"    {summary}")
        print(f"    top5: {row['keyword']['top5']}")
        print()
        results.append(row)

    _print_summary(results, cnames, cats, has_entity)

    if report_path:
        md = generate_report(cfg.title, results, cnames, cats, n, has_entity)
        rpt = Path(report_path)
        rpt.parent.mkdir(parents=True, exist_ok=True)
        rpt.write_text(md)
        print(f"\nMarkdown report → {report_path}")

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
        print(f"Full results → {out_path}")

    print("\nBenchmark complete.")


# ── Console summary ────────────────────────────────────────────────────────

def _print_summary(results, cnames, cats, has_entity):
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    def _ma_attr(c, key, rows=None):
        rows = rows or results
        return avg([r[c]["attr_metrics"][key] for r in rows])
    def _ma_ent(c, key, rows=None):
        rows = rows or results
        vals = [r[c]["entity_metrics"].get(key) for r in rows
                if r[c]["entity_metrics"]]
        return avg([v for v in vals if v is not None])

    print(f"\n{DIV}")
    print("RESULTS — Attribute-level (Hit@K / MRR)")
    print(DIV)
    col_w = 12
    print(f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames))
    print(DIV2)
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        line = f"{label:<20}"
        for c in cnames:
            line += f"{_ma_attr(c, key):>{col_w}.3f}"
        print(line)

    if has_entity:
        print(f"\n{DIV}")
        print("RESULTS — Entity-level (P / R / F1)")
        print(DIV)
        print(f"{'Metric':<20}" + "".join(f"{c:>{col_w}}" for c in cnames))
        print(DIV2)
        for k in ENTITY_K_VALUES:
            for metric, label in [("f1","F1"), ("p","P"), ("r","R")]:
                key = f"{metric}@{k}"
                line = f"{key:<20}"
                for c in cnames:
                    line += f"{_ma_ent(c, key):>{col_w}.3f}"
                print(line)
        print(f"{'f1@ideal':<20}" + "".join(
            f"{_ma_ent(c, 'f1@ideal'):>{col_w}.3f}" for c in cnames))

    print(f"\n── By category ──")
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        line = f"  {cat:<16}"
        for c in cnames:
            h1 = _ma_attr(c, "hit@1", cat_rows)
            line += f"  H@1={h1:.0%}"
            if has_entity:
                f1 = _ma_ent(c, "f1@ideal", cat_rows)
                line += f"  F1@ideal={f1:.2f}"
        print(line + f"  n={len(cat_rows)}")


# ── Markdown report ────────────────────────────────────────────────────────

def generate_report(title, results, cnames, cats, n, has_entity) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    def _ma_attr(c, key, rows=None):
        rows = rows or results
        return avg([r[c]["attr_metrics"][key] for r in rows])
    def _ma_ent(c, key, rows=None):
        rows = rows or results
        vals = [r[c]["entity_metrics"].get(key) for r in rows
                if r[c]["entity_metrics"]]
        return avg([v for v in vals if v is not None])
    def _pct(v): return f"{v:.0%}"
    def _bar(v, width=15):
        filled = round(v * width)
        return "█" * filled + "░" * (width - filled)

    lines: list[str] = []
    a = lines.append

    a(f"# {title} — Results")
    a("")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in cnames)}  ")
    a(f"**Queries:** {n}  ")
    a(f"**Last run:** {now}")
    a("")
    a("> Two evaluation levels: **attribute-level** Hit@K (which column/table?) "
      "and **entity-level** P/R/F1 (which set of tables?). "
      "Entity-level is comparable to MEW, CORE-T, DMRAL.")
    a("")
    a("---")
    a("")

    # ── Attribute-level table ──
    a("## Attribute-level retrieval (Hit@K / MRR)")
    a("")
    a("> Does the relevant column or table appear in the top-K results?")
    a("")
    hdr = "| Metric |" + "".join(f" {c} |" for c in cnames)
    sep = "|--------|" + "".join("---------|" for _ in cnames)
    a(hdr); a(sep)
    for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
        row = f"| {label} |"
        for c in cnames:
            row += f" {_pct(_ma_attr(c, key))} |"
        a(row)
    a("")

    if len(cnames) > 1:
        a("| Metric | Δ keyword → hybrid |")
        a("|--------|--------------------|")
        for label, key in [("Hit@1","hit@1"),("Hit@3","hit@3"),("Hit@5","hit@5"),("MRR","mrr")]:
            b = _ma_attr("keyword", key); h = _ma_attr("hybrid", key)
            sign = "+" if h >= b else ""
            a(f"| {label} | **{sign}{h-b:.3f}** ({_pct(b)} → {_pct(h)}) |")
        a("")

    a("```")
    a(f"Hit@5 (% of {n} queries)")
    a("")
    for c in cnames:
        v = _ma_attr(c, "hit@5")
        a(f"  {c:<14}  {_bar(v)}  {_pct(v):>4}")
    a("```")
    a("")
    a("---")
    a("")

    # ── Entity-level table ──
    if has_entity:
        a("## Entity-level retrieval (P / R / F1)")
        a("")
        a("> Does the search return the right **set of tables** (entity records)?  ")
        a("> Ideal-K uses exactly |relevant tables| as the cutoff — directly comparable to MEW.")
        a("")
        hdr = "| Metric |" + "".join(f" {c} |" for c in cnames)
        sep = "|--------|" + "".join("---------|" for _ in cnames)
        a(hdr); a(sep)
        for k in ENTITY_K_VALUES:
            for metric, label in [("f1", f"F1@{k}"), ("p", f"P@{k}"), ("r", f"R@{k}")]:
                key = f"{metric}@{k}"
                row = f"| {label} |"
                for c in cnames:
                    row += f" {_ma_ent(c, key):.3f} |"
                a(row)
        row = "| F1@Ideal-K |"
        for c in cnames:
            row += f" {_ma_ent(c, 'f1@ideal'):.3f} |"
        a(row)
        row = "| P@Ideal-K |"
        for c in cnames:
            row += f" {_ma_ent(c, 'p@ideal'):.3f} |"
        a(row)
        row = "| R@Ideal-K |"
        for c in cnames:
            row += f" {_ma_ent(c, 'r@ideal'):.3f} |"
        a(row)
        a("")

        if len(cnames) > 1:
            a("| Metric | Δ keyword → hybrid |")
            a("|--------|--------------------|")
            for label, key in [("F1@Ideal-K","f1@ideal"),("P@Ideal-K","p@ideal"),("R@Ideal-K","r@ideal")]:
                b = _ma_ent("keyword", key); h = _ma_ent("hybrid", key)
                sign = "+" if h >= b else ""
                a(f"| {label} | **{sign}{h-b:.3f}** ({b:.3f} → {h:.3f}) |")
            a("")

        a("---")
        a("")

    # ── By category ──
    a("## Results by category")
    a("")
    hdr = "| Category | n |"
    sep = "|---|---|"
    for c in cnames:
        hdr += f" {c} Hit@1 | {c} MRR |"
        sep  += "---|---|"
        if has_entity:
            hdr += f" {c} F1@Ideal |"
            sep  += "---|"
    a(hdr); a(sep)
    for cat in cats:
        cat_rows = [r for r in results if r["category"] == cat]
        nc = len(cat_rows)
        row = f"| {cat} | {nc} |"
        for c in cnames:
            row += f" {_pct(_ma_attr(c, 'hit@1', cat_rows))} | {_ma_attr(c, 'mrr', cat_rows):.2f} |"
            if has_entity:
                row += f" {_ma_ent(c, 'f1@ideal', cat_rows):.2f} |"
        a(row)
    a("")
    a("---")
    a("")

    # ── Per-question ──
    a("## Per-question results")
    a("")
    hdr = "| ID | Cat | Intent"
    sep = "|---|---|---"
    for c in cnames:
        hdr += f" | {c} H@1 | {c} MRR"
        sep  += " |---|---"
        if has_entity:
            hdr += f" | {c} F1@Ideal"
            sep  += " |---"
    hdr += " |"; sep += " |"
    a(hdr); a(sep)
    for r in results:
        intent_short = r["intent"][:52] + "…" if len(r["intent"]) > 52 else r["intent"]
        row = f"| {r['id']} | {r['category']} | {intent_short}"
        for c in cnames:
            h1  = "✅" if r[c]["attr_metrics"]["hit@1"] else "❌"
            mrr = r[c]["attr_metrics"]["mrr"]
            row += f" | {h1} | {mrr:.2f}"
            if has_entity and r[c]["entity_metrics"]:
                f1 = r[c]["entity_metrics"].get("f1@ideal", 0.0)
                row += f" | {f1:.2f}"
            elif has_entity:
                row += " | —"
        row += " |"
        a(row)
    a("")

    return "\n".join(lines)


# ── CLI helpers ────────────────────────────────────────────────────────────

def add_common_args(p):
    p.add_argument("--embed-model", default="text-embedding-3-small")
    p.add_argument("--out", default=None)
    p.add_argument("--report", default=None, nargs="?", const="auto")
    p.add_argument("--page-size", type=int, default=10)
    p.add_argument("--embed-delay", type=float, default=0.1)
    return p
