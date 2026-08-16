# NL2Q Benchmark — 1-shot vs Tool-based

Model: `claude-haiku-4-5-20251001`  |  Dataset: Northwind SQLite  |  Questions: 10

## Summary

| Metric | 1-shot | Tool-based |
|---|---|---|
| Accuracy | 9/10 (90%) | 10/10 (100%) |
| Avg latency | 0.88s | 4.80s |
| Avg LLM calls | 1.0 | 4.1 |

## Per-question results

| # | Question | Category | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |
|---|---|---|---|---|---|---|---|---|
| 1 | How many customers are from Germany? | filter | ✓ | ✓ | 0.84s | 4.75s | 1 | 4 |
| 2 | What is the average freight cost across all orders? | aggregation | ✓ | ✓ | 0.68s | 4.38s | 1 | 4 |
| 3 | How many products are discontinued? | filter | ✓ | ✓ | 0.67s | 3.98s | 1 | 4 |
| 4 | What is the most expensive product? | sort | ✓ | ✓ | 0.82s | 3.98s | 1 | 4 |
| 5 | How many orders were placed in July 1996? | temporal | ✓ | ✓ | 0.92s | 4.44s | 1 | 4 |
| 6 | What is the total freight cost for orders shipped to the UK? | aggregation | ✓ | ✓ | 1.02s | 4.15s | 1 | 4 |
| 7 | Which employee handled the most orders? Give their full name. | join | ✓ | ✓ | 0.85s | 5.90s | 1 | 5 |
| 8 | What is the total revenue per product category? | join | ✓ | ✓ | 1.36s | 6.54s | 1 | 4 |
| 9 | How many customers have never placed an order? | existence | ✓ | ✓ | 0.70s | 4.80s | 1 | 4 |
| 10 | What is the average order value? | join | ✗ | ✓ | 0.89s | 5.10s | 1 | 4 |

## Notes

- **1-shot**: schema injected into a single prompt; LLM returns SQL; one round trip.
- **Tool-based**: LLM drives a tool loop (`list_databases`, `get_schema`, `execute_query`, …); multiple round trips allowed.
- Accuracy checker: scalar queries use ±0.5–5 tolerance; ranking queries check top-1 match; join queries check value presence.