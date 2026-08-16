# NL2Q Benchmark — 1-shot vs Tool-based

Model: `claude-haiku-4-5-20251001`  |  Datasets: northwind, finance  |  Questions: 20

## Overall summary

| Metric | 1-shot | Tool-based |
|---|---|---|
| Accuracy | 15/20 (75%) | 20/20 (100%) |
| Avg latency | 0.93s | 5.33s |
| Avg LLM calls | 1.0 | 4.5 |

## Northwind (10 questions)

| Metric | 1-shot | Tool-based |
|---|---|---|
| Accuracy | 8/10 (80%) | 10/10 (100%) |
| Avg latency | 0.84s | 4.64s |
| Avg LLM calls | 1.0 | 4.1 |

| # | Question | Category | Note | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |
|---|---|---|---|---|---|---|---|---|---|
| 1 | How many customers are from Germany? | filter | Simple WHERE + COUNT | ✓ | ✓ | 0.81s | 3.71s | 1 | 4 |
| 2 | What is the average freight cost across all orders? | aggregation | AVG aggregation | ✓ | ✓ | 0.71s | 4.86s | 1 | 4 |
| 3 | How many products are discontinued? | filter | Boolean filter + COUNT | ✓ | ✓ | 0.55s | 4.58s | 1 | 4 |
| 4 | What is the most expensive product? | sort | ORDER BY + LIMIT 1 | ✓ | ✓ | 0.68s | 4.84s | 1 | 4 |
| 5 | How many orders were placed in July 1996? | temporal | Date pattern filter | ✓ | ✓ | 0.86s | 4.94s | 1 | 5 |
| 6 | What is the total freight cost for orders shipped to the UK? | aggregation | SUM with WHERE | ✓ | ✓ | 0.89s | 4.78s | 1 | 4 |
| 7 | Which employee handled the most orders? Give their full name. | join | JOIN + GROUP BY + ORDER BY — employee name | ✗ | ✓ | 0.92s | 4.28s | 1 | 4 |
| 8 | What is the total revenue per product category? | join | 3-table JOIN + revenue formula | ✓ | ✓ | 1.30s | 4.95s | 1 | 4 |
| 9 | How many customers have never placed an order? | existence | NOT IN subquery (existence) | ✓ | ✓ | 0.79s | 4.39s | 1 | 4 |
| 10 | What is the average order value? | join | Subquery + AVG | ✗ | ✓ | 0.93s | 5.05s | 1 | 4 |

## Finance (10 questions)

| Metric | 1-shot | Tool-based |
|---|---|---|
| Accuracy | 7/10 (70%) | 10/10 (100%) |
| Avg latency | 1.02s | 6.02s |
| Avg LLM calls | 1.0 | 4.9 |

| # | Question | Category | Note | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |
|---|---|---|---|---|---|---|---|---|---|
| 1 | How many female clients are there? | filter | Basic gender filter | ✓ | ✓ | 1.04s | 4.79s | 1 | 4 |
| 2 | What is the average loan amount? | aggregation | AVG over loan table | ✓ | ✓ | 1.08s | 4.49s | 1 | 4 |
| 3 | Which district has the highest average salary? | sort | Opaque columns a2/a11 — requires schema grounding | ✓ | ✓ | 0.85s | 7.61s | 1 | 5 |
| 4 | How many loans are currently running with no problems? | filter | Status code C — requires domain code knowledge | ✗ | ✓ | 0.55s | 9.15s | 1 | 7 |
| 5 | What is the total amount of all credit (incoming) transactions? | aggregation | Czech type code PRIJEM — requires code knowledge | ✗ | ✓ | 2.48s | 7.38s | 1 | 6 |
| 6 | How many accounts have a monthly statement frequency? | filter | Czech frequency string — requires code knowledge | ✗ | ✓ | 0.81s | 7.66s | 1 | 6 |
| 7 | What is the average loan duration in months? | aggregation | Simple AVG — clean columns | ✓ | ✓ | 0.91s | 4.73s | 1 | 4 |
| 8 | How many accounts have at least one loan? | existence | Distinct count via subquery or join | ✓ | ✓ | 0.95s | 3.95s | 1 | 4 |
| 9 | What is the largest single transaction amount? | sort | MAX over trans table | ✓ | ✓ | 0.67s | 5.51s | 1 | 5 |
| 10 | How many accounts have no transactions at all? | existence | NOT IN subquery — existence check | ✓ | ✓ | 0.90s | 4.91s | 1 | 4 |

## Notes

- **1-shot**: full schema injected into a single prompt; LLM returns SQL; one round trip.
- **Tool-based**: LLM drives a tool loop (`list_databases`, `get_schema`, `execute_query`, …); multiple round trips; can explore schema and sample data before answering.
- **Finance dataset**: uses opaque column names (`a2`–`a16`) and Czech domain codes (`PRIJEM`/`VYDAJ`, `POPLATEK MESICNE`, status `A`/`B`/`C`/`D`). 1-shot receives raw column names with no hints; tool-based can query sample rows to disambiguate.
- Accuracy checkers: scalar queries use ±0.5–100 tolerance; ranking queries check top-1 match; join queries check value presence.