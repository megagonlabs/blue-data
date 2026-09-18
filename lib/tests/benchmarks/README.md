# Benchmarks

All benchmarks live in this directory. Results files are committed alongside the scripts.

---

## Search & Discovery

### Finance Discovery (`finance_discovery_benchmark.py`)

Measures attribute-level retrieval quality on the Czech banking dataset.
**80 queries** across 7 categories (aggregation, filter, join, temporal, concept, schema, attribute).

| Condition | Hit@1 | Hit@5 | MRR |
|-----------|-------|-------|-----|
| keyword   | 28%   | 62%   | 41% |
| hybrid    | 40%   | 69%   | 54% |

```bash
# keyword-only
python3 lib/tests/benchmarks/finance_discovery_benchmark.py

# keyword + hybrid
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/finance_discovery_benchmark.py
```

**Report:** [FINANCE_DISCOVERY_RESULTS.md](FINANCE_DISCOVERY_RESULTS.md)

---

### Northwind Discovery (`northwind_discovery_benchmark.py`)

Measures attribute-level retrieval quality on the Northwind e-commerce dataset.
**80 queries** across 8 categories (aggregation, attribute, concept, existence, filter, join, schema, temporal).

| Condition | Hit@1 | Hit@5 | MRR |
|-----------|-------|-------|-----|
| keyword   | 56%   | 65%   | 63% |
| hybrid    | 82%   | 95%   | 86% |

```bash
python3 lib/tests/benchmarks/northwind_discovery_benchmark.py
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/northwind_discovery_benchmark.py
```

**Report:** [NORTHWIND_DISCOVERY_RESULTS.md](NORTHWIND_DISCOVERY_RESULTS.md)

---

### Finance Set Retrieval (`finance_set_benchmark.py`)

Two-level evaluation on Finance: attribute-level Hit@K/MRR **and** entity-level P/R/F1@K.
Entity-level F1@Ideal-K measures whether the right *set of tables* was retrieved.

| Condition | Hit@1 | Hit@5 | F1@Ideal-K |
|-----------|-------|-------|------------|
| keyword   | 28%   | 59%   | 0.17       |

```bash
python3 lib/tests/benchmarks/finance_set_benchmark.py
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/finance_set_benchmark.py
```

**Report:** [FINANCE_SET_RESULTS.md](FINANCE_SET_RESULTS.md)

---

### Northwind Set Retrieval (`northwind_set_benchmark.py`)

Two-level evaluation on Northwind: attribute-level Hit@K/MRR **and** entity-level P/R/F1@K.

| Condition | Hit@1 | Hit@5 | F1@Ideal-K |
|-----------|-------|-------|------------|
| keyword   | 56%   | 73%   | 0.41       |

```bash
python3 lib/tests/benchmarks/northwind_set_benchmark.py
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/northwind_set_benchmark.py
```

**Report:** [NORTHWIND_SET_RESULTS.md](NORTHWIND_SET_RESULTS.md)

---

### BIRD Set Retrieval (`bird_set_benchmark.py`)

Entity-level P/R/F1 on the full BIRD dev set — **1,534 questions across 11 SQLite databases**.
Both attribute-level Hit@K/MRR and entity-level F1@Ideal-K are reported per database and overall.

| Condition | Hit@1 | Hit@5 | F1@Ideal-K |
|-----------|-------|-------|------------|
| keyword   | 44%   | 61%   | 0.29       |

```bash
# all 11 databases
python3 lib/tests/benchmarks/bird_set_benchmark.py --report-dir lib/tests/benchmarks/bird_results

# single database
python3 lib/tests/benchmarks/bird_set_benchmark.py --db financial --report-dir lib/tests/benchmarks/bird_results

# hybrid
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/bird_set_benchmark.py --report-dir lib/tests/benchmarks/bird_results
```

SQLite databases must be present in `data/bird/` (not committed due to file size — download BIRD dev set and run `bird_converter.py`).

**Reports:** [bird_results/BIRD_COMBINED_RESULTS.md](bird_results/BIRD_COMBINED_RESULTS.md) + per-database files.

---

### BIRD Data Lake (`bird_lake_benchmark.py`)

All 11 BIRD databases pooled into **one shared registry** (~86 tables, ~9,988 total
records). Each of the 1,534 queries searches the full lake. Scoring uses source-qualified
`(database, table)` pairs — returning `loan` from the wrong database is a miss.

This is the harder, more realistic evaluation: the retriever must identify not just the
right table name but also which of 11 databases it belongs to, competing against
attribute records from all sources simultaneously.

#### Overall results

| Condition | Hit@1 | Hit@5 | MRR  | F1@Lake (Ideal-K) |
|-----------|-------|-------|------|-------------------|
| keyword   | 21%   | 32%   | 0.26 | 0.02              |
| hybrid    | 32%   | 46%   | 0.37 | 0.02              |

#### Per-database breakdown

| Database | kw H@1 | kw H@5 | kw F1 | hyb H@1 | hyb H@5 | hyb F1 |
|----------|--------|--------|-------|---------|---------|--------|
| california_schools | 28% | 40% | 0.23 | 13% | 28% | 0.10 |
| card_games | 31% | 46% | 0.05 | 49% | 55% | 0.14 |
| codebase_community | 25% | 39% | 0.00 | 28% | 42% | 0.00 |
| debit_card_specializing | 23% | 23% | 0.00 | 25% | 45% | 0.00 |
| european_football_2 | 26% | 34% | 0.00 | 21% | 30% | 0.00 |
| financial | 12% | 39% | 0.00 | 42% | 54% | 0.00 |
| formula_1 | 13% | 27% | 0.00 | 24% | 32% | 0.00 |
| student_club | 18% | 24% | 0.00 | 27% | 39% | 0.00 |
| superhero | 32% | 33% | 0.00 | 63% | 80% | 0.00 |
| thrombosis_prediction | 15% | 25% | 0.00 | 20% | 37% | 0.00 |
| toxicology | 13% | 18% | 0.00 | 38% | 59% | 0.00 |

#### Comparison: per-DB vs lake

| Metric | Per-DB keyword | Lake keyword | Lake hybrid |
|--------|---------------|--------------|-------------|
| Hit@1 | 44% | 21% | 32% |
| Hit@5 | 61% | 32% | 46% |
| F1@Ideal-K | 0.29 | 0.02 | 0.02 |

#### Interpreting the results

**Attribute-level (Hit@K)** drops ~50% going from per-DB to lake. Hybrid search recovers
most of the gap — embeddings are especially effective for databases with domain-specific
vocabulary: financial (12%→42%), superhero (32%→63%), toxicology (13%→38%).

**Entity-level (F1@Lake)** collapses to near zero in the lake scenario. With ~9,988
records competing, entity records (tables) are routinely outranked by attribute records
(columns) from all 11 databases. Only databases with very distinctive table names see
non-zero F1: california_schools (3 tables, unique school/county vocabulary) and
card_games. All other databases have generic table names (`users`, `patient`, `member`)
that are common as column names across the full pool.

**Key insight:** F1@Lake is the metric most sensitive to enrichment. Without Layer 2
descriptions, an entity record for `users` has text "users entity" — indistinguishable
from dozens of attribute records with "user" in their name. Adding semantic descriptions
via enrichment is the primary lever to improve entity-level lake retrieval.

**Note on comparability:** DMRAL (the closest published benchmark) uses a pool of
~109,949 tables vs our 86, making our lake an easier retrieval problem. DMRAL reports
F1@3=59.6% on BirdWild with their full retrieval pipeline (which uses table content, not
just metadata). Our lower numbers reflect that we index metadata only — table/column
names and descriptions when enriched. The gap quantifies how much is left on the table
from content-aware retrieval and enrichment.

```bash
# keyword-only
python3 lib/tests/benchmarks/bird_lake_benchmark.py --report-dir lib/tests/benchmarks/bird_results

# keyword + hybrid (requires OPENAI_API_KEY)
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/bird_lake_benchmark.py --report-dir lib/tests/benchmarks/bird_results

# single database's queries against the full lake
python3 lib/tests/benchmarks/bird_lake_benchmark.py --db financial --report-dir lib/tests/benchmarks/bird_results
```

SQLite databases must be present in `data/bird/` (same requirement as `bird_set_benchmark.py`).

**Report:** [bird_results/BIRD_LAKE_RESULTS.md](bird_results/BIRD_LAKE_RESULTS.md)

---

### Search Benchmark (`search_benchmark.py`)

Keyword vs hybrid on **20 Finance queries** (5 categories). The original baseline benchmark.

```bash
python3 lib/tests/benchmarks/search_benchmark.py
OPENAI_API_KEY=sk-... python3 lib/tests/benchmarks/search_benchmark.py
```

**Report:** [SEARCH_RESULTS.md](SEARCH_RESULTS.md)

---

## NL2SQL

### NL2SQL Enrichment Benchmark (`enrichment_benchmark.py`)

Measures semantic correctness improvement from blue-data enrichment on Czech banking.
**25 questions across 7 categories**, each targeting a distinct enrichment feature.

| Points | Condition |
|--------|-----------|
| 1 | SQL runs without error |
| 1 | SQL returns non-empty result |
| 2 | LLM judge confirms semantic correctness (`--judge`) |

```bash
export OPENAI_API_KEY=sk-...

# baseline vs enriched, with LLM judge
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge

# write markdown report
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --report

# also run Layer 2 (LLM-augmented enrichment)
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --layer2

# Anthropic models
export ANTHROPIC_API_KEY=sk-ant-...
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --model claude-haiku-4-5-20251001 --judge-model claude-sonnet-4-6
```

**Report:** [RESULTS.md](RESULTS.md)

---

### NL2Q Benchmark (`nl2q_benchmark.py`)

Compares **1-shot NL2SQL vs tool-based NL2Q** across Northwind and Finance.
Measures accuracy, latency, LLM call count, and error rate.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 lib/tests/benchmarks/nl2q_benchmark.py

# single dataset
python3 lib/tests/benchmarks/nl2q_benchmark.py --dataset northwind
python3 lib/tests/benchmarks/nl2q_benchmark.py --dataset finance
```

**Report:** [NL2Q_RESULTS.md](NL2Q_RESULTS.md)

---

### NL2Q Enrichment Benchmark (`nl2q_enrichment_benchmark.py`)

**2×2 matrix**: enrichment × querying mode on Finance (Czech banking).

| Condition | Description |
|-----------|-------------|
| baseline-1shot | Raw schema, single prompt |
| enriched-1shot | Enriched schema injected into prompt |
| baseline-tools | Tool loop, no enrichment |
| enriched-tools | Tool loop + `get_enriched_metadata` tool |

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 lib/tests/benchmarks/nl2q_enrichment_benchmark.py
```

**Report:** [ENRICHMENT_NL2Q_RESULTS.md](ENRICHMENT_NL2Q_RESULTS.md)

---

## Utilities

### BIRD Converter (`bird_converter.py`)

Converts BIRD `dev.json` to blue-data query files and entity mapping files.

```bash
python3 lib/tests/benchmarks/bird_converter.py /path/to/BIRD/dev.json --out-dir data/bird
python3 lib/tests/benchmarks/bird_converter.py dev.json --out-dir data/bird --db financial
```

### Internal Runners

| File | Used by |
|------|---------|
| `_discovery_runner.py` | `finance_discovery_benchmark.py`, `northwind_discovery_benchmark.py` |
| `_set_retrieval_runner.py` | `finance_set_benchmark.py`, `northwind_set_benchmark.py`, `bird_set_benchmark.py`, `bird_lake_benchmark.py` |

---

## Data files

| File | Description |
|------|-------------|
| `data/finance_sqlite.sql` | Czech banking schema + data (5 tables) |
| `data/northwind_sqlite.sql` | Northwind e-commerce schema + data (7 tables) |
| `data/finance_discovery_queries.json` | 80 Finance discovery queries |
| `data/northwind_discovery_queries.json` | 80 Northwind discovery queries |
| `data/finance_entity_mapping.json` | Finance query → relevant tables mapping |
| `data/northwind_entity_mapping.json` | Northwind query → relevant tables mapping |
| `data/finance_benchmark_queries.json` | 25 NL2SQL enrichment benchmark questions |
| `data/bird/` | BIRD dev queries + entity mappings + 11 SQLite databases |
