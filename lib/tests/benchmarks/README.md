# Benchmarks

## NL2SQL Enrichment Benchmark (`enrichment_benchmark.py`)

Measures the semantic correctness improvement from blue-data enrichment on the Czech
banking dataset. **25 questions across 7 categories**, each targeting a distinct
enrichment feature. Each question was verified to show baseline incorrect → enriched correct
before being added.

### Question categories

| Category | n | What it tests |
|---|---|---|
| `none` | 4 | Control — answerable from column names alone. Both conditions expected correct. |
| `enum_coded_value` | 7 | Czech domain codes (`VKLAD`, `POJISTNE`, `SIPO`, `PREVOD NA UCET`, `loan.status` A/B/C/D…). Baseline generates English words → 0 rows. |
| `opaque_column` | 3 | `district` columns `a2`–`a16` with no meaningful names. Enrichment injects samples and region ENUM values. |
| `current_state` | 3 | `trans.balance` is a running total. "Current balance" = latest row per account, not AVG. |
| `distributional` | 3 | Statistical extreme cutoffs (`amount > 21200`, `balance < 9500`) computed from actual data. |
| `quantitative_misinterpretation` | 3 | Ratio/net-credit queries requiring correct `PRIJEM`/`VYDAJ` codes. |
| `time_grain` | 2 | Monthly aggregations with ENUM-filtered populations. |

### Run

```bash
# --- OpenAI (default) ---
export OPENAI_API_KEY=sk-...

# baseline vs enriched, with LLM judge (recommended)
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge

# write a markdown report with Mermaid charts
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --report

# also run Layer 2 (LLM-augmented enrichment) as a third condition
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --layer2

# save raw JSON results
python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --out results/run.json

# --- Anthropic ---
export ANTHROPIC_API_KEY=sk-ant-...

python3 lib/tests/benchmarks/enrichment_benchmark.py --judge --model claude-haiku-4-5-20251001 --judge-model claude-sonnet-4-6
```

### Scoring

| Points | Condition |
|---|---|
| 1 | SQL runs without error |
| 1 | SQL returns non-empty result |
| 2 | LLM judge confirms semantic correctness (`--judge`) |

Max 4 pts per question with `--judge`, 2 pts without.

### Results

See [RESULTS.md](RESULTS.md) for the latest run: overall table, per-category charts, and per-question verdicts.

### Data files

| File | Description |
|---|---|
| `data/finance_sqlite.sql` | Czech banking schema + data (5 tables) |
| `data/finance_benchmark_queries.json` | 25 benchmark questions with expected behavior |
