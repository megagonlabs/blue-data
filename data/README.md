# Demo data

This directory contains sample datasets used by the examples and benchmarks.

## Northwind

A classic 7-table retail sales schema — categories, customers, employees, orders, order_details, products, and suppliers — with FK relations and sample data. Used by most of the pipeline and scenario demos.

| File | Use |
|---|---|
| `northwind_sqlite.sql` | Load into SQLite: `sqlite3 northwind.db < data/northwind_sqlite.sql` |
| `northwind_postgres.sql` | Load into Postgres: `psql -U postgres -d northwind -f data/northwind_postgres.sql` |
| `northwind_descriptions.json` | Pre-generated Layer 2 descriptions (via `claude-haiku-4-5`) for the Northwind schema — used to skip LLM calls in demos |

## Finance (Czech banking)

A 5-table banking dataset derived from the BIRD benchmark. Intentionally preserves the original opaque column names (`a2`–`a16` in district, `k_symbol` / `operation` / `type` in trans) to demonstrate the value of semantic enrichment — enrichment resolves what the names mean.

Tables: `district`, `client`, `account`, `loan`, `trans`.

| File | Use |
|---|---|
| `finance_sqlite.sql` | Load into SQLite: `sqlite3 finance.db < data/finance_sqlite.sql` |
| `finance_benchmark_queries.json` | Benchmark query set for evaluating NL-to-SQL accuracy against the finance schema |

```bash
sqlite3 finance.db < data/finance_sqlite.sql
```
