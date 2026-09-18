# Demo data

This directory contains sample datasets used by the examples and benchmarks.

## Northwind

A classic 7-table retail sales schema — categories, customers, employees, orders, order_details, products, and suppliers — with FK relations and sample data. Used by most of the pipeline and scenario demos.

| File | Use |
|---|---|
| `northwind_sqlite.sql` | Load into SQLite: `sqlite3 northwind.db < data/northwind_sqlite.sql` |
| `northwind_postgres.sql` | Load into Postgres: `psql -U postgres -d northwind -f data/northwind_postgres.sql` |
| `northwind_descriptions.json` | Pre-generated Layer 2 descriptions (via `claude-haiku-4-5`) for the Northwind schema — used to skip LLM calls in demos |
| `northwind_discovery_queries.json` | 40 natural-language discovery queries against the Northwind schema — used to benchmark registry search recall and ranking |
| `northwind_entity_mapping.json` | Maps each Northwind discovery query ID to the relevant entity names — used to score recall in search benchmarks |

## Finance (Czech banking)

A 5-table banking dataset derived from the BIRD benchmark. Intentionally preserves the original opaque column names (`a2`–`a16` in district, `k_symbol` / `operation` / `type` in trans) to demonstrate the value of semantic enrichment — enrichment resolves what the names mean.

Tables: `district`, `client`, `account`, `loan`, `trans`.

| File | Use |
|---|---|
| `finance_sqlite.sql` | Load into SQLite: `sqlite3 finance.db < data/finance_sqlite.sql` |
| `finance_discovery_queries.json` | 40 natural-language discovery queries against the finance schema — used to benchmark registry search recall and ranking |
| `finance_benchmark_queries.json` | 25 NL-to-SQL benchmark queries for evaluating query accuracy against the finance schema |
| `finance_entity_mapping.json` | Maps each finance discovery query ID to the relevant entity names — used to score recall in search benchmarks |

```bash
sqlite3 finance.db < data/finance_sqlite.sql
```

## BIRD

11 databases from the [BIRD benchmark](https://bird-bench.github.io/) covering diverse domains (schools, finance, sports, biomedical, etc.). Each database ships with discovery queries and an entity mapping for search recall scoring.

| File pattern | Use |
|---|---|
| `bird/<name>.sqlite` | SQLite database |
| `bird/<name>_discovery_queries.json` | Natural-language discovery queries for that database |
| `bird/<name>_entity_mapping.json` | Maps each discovery query ID to relevant entity names |

Databases: `california_schools`, `card_games`, `codebase_community`, `debit_card_specializing`, `european_football_2`, `financial`, `formula_1`, `student_club`, `superhero`, `thrombosis_prediction`, `toxicology`.

## Cross-dataset

| File | Use |
|---|---|
| `search_benchmark_queries.json` | 20 registry search queries spanning both Northwind and finance schemas — used to evaluate hybrid BM25+vector search across mixed-source registries |
