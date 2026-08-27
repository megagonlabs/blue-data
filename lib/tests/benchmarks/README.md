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
| `_set_retrieval_runner.py` | `finance_set_benchmark.py`, `northwind_set_benchmark.py`, `bird_set_benchmark.py` |

---

## Data files

| File | Description |
|------|-------------|
| `data/finance_sqlite.sql` | Czech banking schema + data (8 tables) |
| `data/northwind_sqlite.sql` | Northwind e-commerce schema + data (13 tables) |
| `data/finance_discovery_queries.json` | 80 Finance discovery queries |
| `data/northwind_discovery_queries.json` | 80 Northwind discovery queries |
| `data/finance_entity_mapping.json` | Finance query → relevant tables mapping |
| `data/northwind_entity_mapping.json` | Northwind query → relevant tables mapping |
| `data/finance_benchmark_queries.json` | 25 NL2SQL enrichment benchmark questions |
| `data/bird/` | BIRD dev queries + entity mappings (SQLite DBs excluded — too large) |
