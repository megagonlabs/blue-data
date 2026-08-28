"""BIRD data lake benchmark — all 11 databases pooled into one registry.

Evaluates table retrieval in a true data lake scenario: all ~100 tables from
11 BIRD databases are indexed in a single shared DataRegistry. Each query
searches the full lake and must surface the right tables from the right database.

Scoring uses source-qualified entity pairs — (db_id, table_name) — so returning
"loan" from superhero when the query needs "loan" from financial is a miss.

This is the apples-to-apples comparison with MEW / DMRAL, which also pool tables
from multiple databases before evaluating retrieval.

Dataset : BIRD dev set — 1,534 questions, 11 databases, ~100 tables in the lake
Metrics : entity-level P/R/F1@K and F1@Ideal-K (source-qualified)
          attribute-level Hit@K/MRR (unqualified, same as per-DB benchmark)

Usage:
    # keyword-only
    python bird_lake_benchmark.py --report-dir bird_results/lake

    # hybrid (BM25 + embeddings)
    OPENAI_API_KEY=sk-... python bird_lake_benchmark.py --report-dir bird_results/lake

    # single database's queries against the full lake
    python bird_lake_benchmark.py --db financial --report-dir bird_results/lake
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_BENCH = Path(__file__).parent
_DATA  = Path(__file__).parent.parent.parent.parent / "data" / "bird"

sys.path.insert(0, str(_BENCH))
from _set_retrieval_runner import (
    add_common_args,
    make_openai_embed_fn,
    score_attribute,
    topk_names,
    ENTITY_K_VALUES,
    DIV,
    DIV2,
)

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

DIM = 1536

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

BENCH_CONFIG = {
    "bm25_threshold":       0.0,
    "vector_threshold":     0.0,
    "value_threshold":      0.0,
    "combined_threshold":   0.0,
    "hierarchical_enabled": False,
}


# ── Source-qualified entity scoring ───────────────────────────────────────

def _source_from_scope(scope: str) -> str:
    """Extract source name from registry scope string.

    '/source/financial/database/financial/collection/public' → 'financial'
    """
    parts = scope.split("/")
    try:
        return parts[parts.index("source") + 1]
    except (ValueError, IndexError):
        return ""


def score_lake_entity_set(
    results: list[dict],
    relevant_pairs: set[tuple[str, str]],
    k: int,
) -> dict:
    """P/R/F1 on (source, entity_name) pairs — source-qualified lake scoring."""
    entity_results = [r for r in results[:k] if r.get("type") == "entity"]
    retrieved = {
        (_source_from_scope(r.get("scope", "")), (r.get("name") or "").lower())
        for r in entity_results
        if r.get("name")
    }
    norm_relevant = {(s, n.lower()) for s, n in relevant_pairs}

    if not norm_relevant:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = len(retrieved & norm_relevant)
    precision = tp / len(retrieved) if retrieved else 0.0
    recall    = tp / len(norm_relevant)
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1}


def score_lake_entity_ideal(
    results: list[dict],
    relevant_pairs: set[tuple[str, str]],
) -> dict:
    k = max(1, len(relevant_pairs))
    return score_lake_entity_set(results, relevant_pairs, k)


# ── Build pooled lake registry ─────────────────────────────────────────────

def _batch_embed_registry(reg: DataRegistry, openai_client, model: str) -> None:
    """Embed all registry records in a single batched OpenAI API call."""
    indexer = reg.search_engine.indexer
    if indexer.vector_source is None:
        return
    indexer.ensure_index()

    records = reg.get_records()
    items = []
    for r in records:
        text        = indexer._record_text(r)
        schema_text = indexer._schema_text(r)
        if text:
            items.append((r, text, schema_text))

    if not items:
        return

    # Collect all texts; schema_text is a second embedding per record when present
    all_texts = []
    for _, text, schema_text in items:
        all_texts.append(text)
        if schema_text:
            all_texts.append(schema_text)

    print(f"  Batch embedding {len(all_texts)} texts ({len(items)} records) …")
    # OpenAI accepts up to 2048 inputs; chunk just in case
    chunk_size = 2000
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), chunk_size):
        resp = openai_client.embeddings.create(
            input=all_texts[i:i + chunk_size], model=model
        )
        all_embeddings.extend(e.embedding for e in resp.data)

    idx = 0
    for r, text, schema_text in items:
        name  = r.get("name", "")
        rtype = r.get("type", "")
        scope = r.get("scope", "/")
        doc   = {
            "embedding":   all_embeddings[idx],
            "name":        name,
            "type":        rtype,
            "scope":       scope,
            "description": r.get("description", ""),
        }
        idx += 1
        if schema_text:
            doc["schema_embedding"] = all_embeddings[idx]
            idx += 1
        indexer.vector_source.execute_query({
            "op":              "VECTOR.UPSERT",
            "collection":      indexer.collection,
            "id":              f"{scope}/{rtype}/{name}",
            "doc":             doc,
            "embedding_field": "embedding",
        })


def build_lake_registry(
    lake_dir: str,
    databases: list[str],
    openai_client=None,
    embed_model: str = "text-embedding-3-small",
    embedding_fn=None,
) -> DataRegistry:
    vector_source = MemoryVectorSource() if openai_client else None
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=vector_source,
        embedding_fn=embedding_fn,   # kept for query-time embedding
        vector_dim=DIM if openai_client else None,
        rebuild=False,               # no per-record embedding during sync
        hybrid_config=BENCH_CONFIG,
    )
    for db in databases:
        db_path = os.path.join(lake_dir, f"{db}.db")
        if not os.path.exists(db_path):
            continue
        source = SQLiteDBSource(
            name=db,
            properties={"connection": {"database_directory": lake_dir}},
        )
        reg.register_source(source)
    reg.sync_all(recursive=True)

    if openai_client:
        _batch_embed_registry(reg, openai_client, embed_model)

    return reg


# ── Main run ───────────────────────────────────────────────────────────────

def run_lake(
    databases: list[str],
    embed_model: str,
    report_dir: Path | None,
    page_size: int,
    embed_delay: float,
) -> None:
    openai_key = os.environ.get("OPENAI_API_KEY")
    openai_client = None
    embedding_fn  = None
    if openai_key:
        import openai as _openai
        openai_client = _openai.OpenAI(api_key=openai_key)
        embedding_fn  = make_openai_embed_fn(openai_key, embed_model)

    conditions = ["keyword"] + (["hybrid"] if openai_client else [])

    # Copy all available SQLite files into a shared temp dir as .db files
    lake_dir = tempfile.mkdtemp(prefix="bird-lake-")
    available_dbs = []
    for db in DATABASES:
        src = _DATA / f"{db}.sqlite"
        if src.exists():
            shutil.copy(src, os.path.join(lake_dir, f"{db}.db"))
            available_dbs.append(db)

    total_tables = sum(
        len(json.loads((_DATA / f"{db}_entity_mapping.json").read_text()))
        for db in available_dbs
        if (_DATA / f"{db}_entity_mapping.json").exists()
    )

    print()
    print(DIV)
    print(f"BIRD Data Lake Benchmark")
    print(f"  Databases in lake : {len(available_dbs)}")
    print(f"  Conditions        : {', '.join(conditions)}")
    if openai_client:
        print(f"  Embed model       : {embed_model}")
    print(DIV)

    # Build lake registries.
    # Keyword: sync only, no embedding (fast).
    # Hybrid: same sync + one batched OpenAI call for all records (fast).
    registries: dict[str, DataRegistry] = {}
    print(f"\nBuilding keyword lake registry ({len(available_dbs)} sources) …")
    registries["keyword"] = build_lake_registry(lake_dir, available_dbs)
    if openai_client:
        print(f"Building hybrid lake registry (batch embed) …")
        registries["hybrid"] = build_lake_registry(
            lake_dir, available_dbs,
            openai_client=openai_client,
            embed_model=embed_model,
            embedding_fn=embedding_fn,
        )

    # Run queries — only for the requested databases
    all_rows: list[dict] = []
    db_summaries: list[dict] = []

    query_dbs = [db for db in databases if db in available_dbs]

    for db in query_dbs:
        queries_file = _DATA / f"{db}_discovery_queries.json"
        em_file      = _DATA / f"{db}_entity_mapping.json"
        if not queries_file.exists():
            continue

        queries    = json.loads(queries_file.read_text())
        entity_map = json.loads(em_file.read_text()) if em_file.exists() else {}
        n          = len(queries)

        print(f"\n── {db} ({n} queries) ──")

        db_rows: list[dict] = []
        for i, q in enumerate(queries, 1):
            relevant_names  = set(q.get("relevant_names", []))
            # Source-qualified pairs: the db_id is always the source for BIRD queries
            relevant_pairs  = {
                (db, t) for t in entity_map.get(q["id"], [])
            }

            row: dict = {
                "id":              q["id"],
                "intent":          q["intent"],
                "category":        q["category"],
                "db":              db,
                "relevant_names":  q.get("relevant_names", []),
                "relevant_pairs":  [(s, t) for s, t in relevant_pairs],
            }

            for cname, reg in registries.items():
                # page_limit controls search_limit (= page_limit * page_size).
                # With ~880 records in the lake, default page_limit=10 would only
                # score the first 100 records. Set high enough to cover all records.
                sr     = reg.search_records(q["intent"], page_size=page_size, page_limit=200)
                attr_m = score_attribute(sr, relevant_names)
                lake_m = {}
                if relevant_pairs:
                    for k in ENTITY_K_VALUES:
                        lm = score_lake_entity_set(sr, relevant_pairs, k)
                        lake_m[f"p@{k}"]  = lm["precision"]
                        lake_m[f"r@{k}"]  = lm["recall"]
                        lake_m[f"f1@{k}"] = lm["f1"]
                    ideal = score_lake_entity_ideal(sr, relevant_pairs)
                    lake_m["p@ideal"]  = ideal["precision"]
                    lake_m["r@ideal"]  = ideal["recall"]
                    lake_m["f1@ideal"] = ideal["f1"]

                row[cname] = {
                    "attr_metrics": attr_m,
                    "lake_metrics": lake_m,
                    "top5":         topk_names(sr, 5),
                    "top5_sources": [
                        _source_from_scope(r.get("scope", ""))
                        for r in sr[:5]
                        if r.get("type") == "entity"
                    ],
                }

            db_rows.append(row)
            all_rows.append(row)

            if i % 50 == 0 or i == n:
                def avg(lst): return sum(lst) / len(lst) if lst else 0.0
                h1  = avg([r[conditions[0]]["attr_metrics"]["hit@1"] for r in db_rows])
                f1i = avg([
                    r[conditions[0]]["lake_metrics"].get("f1@ideal", 0)
                    for r in db_rows if r[conditions[0]]["lake_metrics"]
                ])
                print(f"  [{i:4}/{n}]  keyword H@1={h1:.0%}  F1@Ideal={f1i:.2f}")

        def avg(lst): return sum(lst) / len(lst) if lst else 0.0
        summary = {}
        for c in conditions:
            summary[c] = {
                "hit@1":    avg([r[c]["attr_metrics"]["hit@1"] for r in db_rows]),
                "hit@5":    avg([r[c]["attr_metrics"]["hit@5"] for r in db_rows]),
                "mrr":      avg([r[c]["attr_metrics"]["mrr"]   for r in db_rows]),
                "f1@ideal": avg([
                    r[c]["lake_metrics"].get("f1@ideal", 0)
                    for r in db_rows if r[c]["lake_metrics"]
                ]),
            }
        db_summaries.append({"db": db, "n": n, **summary})

        for c in conditions:
            s = summary[c]
            print(f"  [{c}] H@1={s['hit@1']:.0%}  H@5={s['hit@5']:.0%}"
                  f"  MRR={s['mrr']:.2f}  F1@Ideal(lake)={s['f1@ideal']:.2f}")

    _print_combined(db_summaries, conditions, all_rows)

    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        _write_report(db_summaries, conditions, all_rows, report_dir)

    shutil.rmtree(lake_dir, ignore_errors=True)


# ── Console summary ────────────────────────────────────────────────────────

def _print_combined(summaries, conditions, all_rows):
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0

    total = sum(s["n"] for s in summaries)
    print(f"\n{DIV}")
    print(f"BIRD LAKE — COMBINED   {total} queries   {len(summaries)} databases")
    print(DIV)
    print(f"\n{'DB':<30}" + "".join(
        f"  {c} H@1   H@5   MRR  F1@Lake" for c in conditions))
    print(DIV2)
    for s in summaries:
        line = f"{s['db']:<30}"
        for c in conditions:
            if c in s:
                line += (f"  {s[c]['hit@1']:>4.0%}  {s[c]['hit@5']:>4.0%}"
                         f"  {s[c]['mrr']:.2f}    {s[c]['f1@ideal']:.2f}")
        print(line)
    print(DIV2)
    line = f"{'OVERALL':<30}"
    for c in conditions:
        def _a(k): return avg([r[c]["attr_metrics"][k] for r in all_rows])
        def _e(k):
            vals = [r[c]["lake_metrics"].get(k) for r in all_rows
                    if r[c]["lake_metrics"]]
            return avg([v for v in vals if v is not None])
        line += (f"  {_a('hit@1'):>4.0%}  {_a('hit@5'):>4.0%}"
                 f"  {_a('mrr'):.2f}    {_e('f1@ideal'):.2f}")
    print(line)
    print()
    print("Note: F1@Lake uses source-qualified (db, table) pairs.")
    print("      A result must come from the correct database to count as a hit.")


# ── Markdown report ────────────────────────────────────────────────────────

def _write_report(summaries, conditions, all_rows, report_dir: Path):
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(s["n"] for s in summaries)

    lines = []
    a = lines.append

    a("# BIRD Data Lake Benchmark — Results")
    a("")
    a(f"**Setup:** All {len(summaries)} BIRD databases pooled into one shared registry (~100 tables total).  ")
    a(f"**Queries:** {total} questions — each searched against the full lake.  ")
    a(f"**Conditions:** {', '.join(f'`{c}`' for c in conditions)}  ")
    a(f"**Last run:** {now}")
    a("")
    a("> **F1@Lake** uses source-qualified `(database, table)` pairs.")
    a("> Returning `loan` from the wrong database counts as a false positive.")
    a("> Ideal-K uses exactly |relevant tables| as the cutoff.")
    a("")
    a("---")
    a("")
    a("## Overall")
    a("")
    hdr = "| Metric |" + "".join(f" {c} |" for c in conditions)
    sep = "|---|" + "".join("---|" for _ in conditions)
    a(hdr); a(sep)
    for label, key, is_lake in [
        ("Hit@1",       "hit@1", False),
        ("Hit@5",       "hit@5", False),
        ("MRR",         "mrr",   False),
        ("F1@Ideal-K (lake)", "f1@ideal", True),
    ]:
        row = f"| {label} |"
        for c in conditions:
            if is_lake:
                vals = [r[c]["lake_metrics"].get(key) for r in all_rows
                        if r[c]["lake_metrics"]]
                v = avg([x for x in vals if x is not None])
                row += f" {v:.3f} |"
            else:
                v = avg([r[c]["attr_metrics"][key] for r in all_rows])
                row += f" {v:.0%} |"
        a(row)
    a("")
    a("---")
    a("")
    a("## Per-database")
    a("")
    hdr = "| Database | n |"
    sep = "|---|---|"
    for c in conditions:
        hdr += f" {c} H@1 | {c} H@5 | {c} MRR | {c} F1@Lake |"
        sep  += "---|---|---|---|"
    a(hdr); a(sep)
    for s in summaries:
        row = f"| {s['db']} | {s['n']} |"
        for c in conditions:
            if c in s:
                row += (f" {s[c]['hit@1']:.0%} | {s[c]['hit@5']:.0%}"
                        f" | {s[c]['mrr']:.2f} | {s[c]['f1@ideal']:.2f} |")
        a(row)
    a("")
    a("---")
    a("")
    a("## Comparison: per-DB vs lake")
    a("")
    a("Per-DB benchmark scores each query against only its own database's registry.")
    a("Lake benchmark scores the same query against all 11 databases pooled together.")
    a("The gap shows how much retrieval degrades in the presence of cross-database noise.")
    a("")

    rp = report_dir / "BIRD_LAKE_RESULTS.md"
    rp.write_text("\n".join(lines))
    print(f"\nReport → {rp}")


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=None,
                   help="Run only this database's queries (default: all)")
    p.add_argument("--report-dir", default=None,
                   help="Directory to write the lake results report")
    add_common_args(p)
    args = p.parse_args()

    dbs = [args.db] if args.db else DATABASES
    report_dir = Path(args.report_dir) if args.report_dir else None

    run_lake(
        databases=dbs,
        embed_model=args.embed_model,
        report_dir=report_dir,
        page_size=args.page_size,
        embed_delay=args.embed_delay,
    )
