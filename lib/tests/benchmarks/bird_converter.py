"""Convert BIRD benchmark JSON to blue-data query + entity-mapping format.

BIRD format (dev.json / test.json):
  [
    {
      "question_id": 0,
      "db_id": "california_schools",
      "question": "What is the highest eligible free rate for K-12...",
      "SQL": "SELECT ... FROM frpm WHERE ...",
      ...
    },
    ...
  ]

Outputs two files per database:
  - {db_id}_discovery_queries.json   — query file (relevant_names = all tables in SQL)
  - {db_id}_entity_mapping.json      — entity mapping (same tables, for P/R/F1)

Usage:
    python bird_converter.py dev.json --out-dir ./bird_data
    python bird_converter.py dev.json --out-dir ./bird_data --db california_schools
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# ── SQL table extractor ────────────────────────────────────────────────────

_FROM_RE  = re.compile(
    r"\bFROM\s+([\w`"\[\]]+)",
    re.IGNORECASE,
)
_JOIN_RE  = re.compile(
    r"\bJOIN\s+([\w`"\[\]]+)",
    re.IGNORECASE,
)

def _strip_quotes(name: str) -> str:
    return name.strip("`\"[]")


def extract_tables(sql: str) -> list[str]:
    """Return unique table names referenced in a SQL statement."""
    tables: dict[str, None] = {}
    for m in _FROM_RE.finditer(sql):
        t = _strip_quotes(m.group(1))
        if t.lower() not in ("select", "where", "("):
            tables[t.lower()] = None
    for m in _JOIN_RE.finditer(sql):
        t = _strip_quotes(m.group(1))
        tables[t.lower()] = None
    return list(tables.keys())


# ── Converter ──────────────────────────────────────────────────────────────

def convert(
    bird_path: Path,
    out_dir: Path,
    only_db: str | None = None,
) -> dict[str, dict]:
    data = json.loads(bird_path.read_text())

    by_db: dict[str, list[dict]] = defaultdict(list)
    for item in data:
        db = item.get("db_id", "unknown")
        if only_db and db != only_db:
            continue
        by_db[db].append(item)

    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for db, items in sorted(by_db.items()):
        queries      = []
        entity_map   = {}

        for idx, item in enumerate(items, 1):
            qid       = f"bird_{db}_{idx:03d}"
            sql       = item.get("SQL", "") or item.get("sql", "")
            tables    = extract_tables(sql)
            question  = item.get("question", "")
            evidence  = item.get("evidence", "")

            # relevant_names: column-level discovery uses table names as proxies
            relevant_names = tables or []

            queries.append({
                "id":             qid,
                "intent":         question,
                "category":       "bird",
                "relevant_names": relevant_names,
                "primary_name":   relevant_names[0] if relevant_names else "",
                "description":    evidence,
                "source_sql":     sql,
            })
            entity_map[qid] = relevant_names

        q_path  = out_dir / f"{db}_discovery_queries.json"
        em_path = out_dir / f"{db}_entity_mapping.json"
        q_path .write_text(json.dumps(queries,     indent=2))
        em_path.write_text(json.dumps(entity_map,  indent=2))

        results[db] = {"n": len(queries), "q_path": str(q_path), "em_path": str(em_path)}
        print(f"  {db:30s}  {len(queries):4d} queries → {q_path.name}")

    return results


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bird_json", help="Path to BIRD dev.json or test.json")
    p.add_argument("--out-dir", default="./bird_data", help="Output directory")
    p.add_argument("--db",      default=None, help="Convert only this db_id")
    args = p.parse_args()

    bird_path = Path(args.bird_json)
    if not bird_path.exists():
        print(f"ERROR: {bird_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Converting {bird_path.name} …")
    res = convert(bird_path, Path(args.out_dir), only_db=args.db)
    total = sum(v["n"] for v in res.values())
    print(f"\nDone: {len(res)} database(s), {total} queries total.")
    print(f"Output dir: {Path(args.out_dir).resolve()}")
