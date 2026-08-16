# NL2Q Benchmark — 1-shot vs Tool-based

Model: `claude-haiku-4-5-20251001`  |  Dataset: Northwind SQLite  |  Questions: 10

## Summary

| Metric | 1-shot | Tool-based |
|---|---|---|
| Accuracy | 8/10 (80%) | 10/10 (100%) |
| Avg latency | 0.91s | 5.03s |
| Avg LLM calls | 1.0 | 4.3 |

## Per-question results

| # | Question | Category | 1-shot | Tool | 1-shot lat | Tool lat | 1-shot calls | Tool calls |
|---|---|---|---|---|---|---|---|---|
| 1 | How many customers are from Germany? | filter | ✓ | ✓ | 0.75s | 4.26s | 1 | 4 |
| 2 | What is the average freight cost across all orders? | aggregation | ✓ | ✓ | 0.67s | 4.34s | 1 | 4 |
| 3 | How many products are discontinued? | filter | ✓ | ✓ | 0.58s | 4.26s | 1 | 4 |
| 4 | What is the most expensive product? | sort | ✓ | ✓ | 0.76s | 4.72s | 1 | 4 |
| 5 | How many orders were placed in July 1996? | temporal | ✓ | ✓ | 1.00s | 4.29s | 1 | 4 |
| 6 | What is the total freight cost for orders shipped to the UK? | aggregation | ✓ | ✓ | 1.17s | 5.23s | 1 | 5 |
| 7 | Which employee handled the most orders? Give their full name. | join | ✗ | ✓ | 0.95s | 6.12s | 1 | 5 |
| 8 | What is the total revenue per product category? | join | ✓ | ✓ | 1.69s | 6.81s | 1 | 5 |
| 9 | How many customers have never placed an order? | existence | ✓ | ✓ | 0.62s | 4.90s | 1 | 4 |
| 10 | What is the average order value? | join | ✗ | ✓ | 0.86s | 5.39s | 1 | 4 |

## Notes

- **1-shot**: schema injected into a single prompt; LLM returns SQL; one round trip.
- **Tool-based**: LLM drives a tool loop (`list_databases`, `get_schema`, `execute_query`, …); multiple round trips allowed.
- Accuracy checker: scalar queries use ±0.5–5 tolerance; ranking queries check top-1 match; join queries check value presence.