# NL2Q Enrichment Benchmark — 2×2 Matrix

Model: `claude-haiku-4-5-20251001`  |  Total questions: 35

## Conditions

| Label | Description |
|---|---|
| Baseline 1-shot | Raw schema injected into a single prompt; no enrichment |
| Enriched 1-shot | Enriched schema with semantic types and sample values injected |
| Baseline tools  | Tool loop (list, get_schema, execute_query); no enrichment |
| Enriched tools  | Tool loop + `get_enriched_metadata` registry tool available |

## Finance (20 questions)

### Condition summary

| Condition | Accuracy | Avg latency | Avg LLM calls |
|---|---|---|---|
| Baseline 1-shot | 10/20 (50%) | 0.74s | 1.0 |
| Enriched 1-shot | 15/20 (75%) | 0.80s | 1.0 |
| Baseline tools | 18/20 (90%) | 6.98s | 5.2 |
| Enriched tools | 20/20 (100%) | 7.36s | 5.7 |

### Enrichment-sensitive questions (13 of 20)

| Condition | Accuracy |
|---|---|
| Baseline 1-shot | 3/13 (23%) |
| Enriched 1-shot | 8/13 (61%) |
| Baseline tools | 11/13 (84%) |
| Enriched tools | 13/13 (100%) |

### Per-question results

| # | Question | Sensitive | Baseline 1-shot | Enriched 1-shot | Baseline tools | Enriched tools |
|---|---|---| --- | --- | --- | --- |
| 1 | How many female clients are there? |  | ✓ (1 calls, 0.8s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.7s) | ✓ (4 calls, 3.9s) |
| 2 | What is the average loan amount? |  | ✓ (1 calls, 0.9s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.8s) | ✓ (4 calls, 4.9s) |
| 3 | Which district has the highest average salary? | ★ | ✓ (1 calls, 1.0s) | ✓ (1 calls, 0.8s) | ✓ (5 calls, 7.2s) | ✓ (6 calls, 8.1s) |
| 4 | How many loans are currently running with no problems? | ★ | ✗ (1 calls, 0.6s) | ✗ (1 calls, 0.7s) | ✗ (6 calls, 9.3s) | ✓ (7 calls, 9.9s) |
| 5 | What is the total amount of all credit (incoming) transactions? | ★ | ✓ (1 calls, 0.8s) | ✓ (1 calls, 0.6s) | ✓ (5 calls, 7.3s) | ✓ (5 calls, 7.5s) |
| 6 | How many accounts have a monthly statement frequency? | ★ | ✗ (1 calls, 0.6s) | ✓ (1 calls, 0.9s) | ✓ (5 calls, 5.6s) | ✓ (6 calls, 6.9s) |
| 7 | What is the average loan duration in months? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 4.1s) | ✓ (6 calls, 6.2s) |
| 8 | How many accounts have at least one loan? |  | ✓ (1 calls, 0.8s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 4.5s) | ✓ (4 calls, 5.7s) |
| 9 | What is the largest single transaction amount? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 5.1s) | ✓ (4 calls, 4.0s) |
| 10 | How many accounts have no transactions at all? |  | ✓ (1 calls, 0.8s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 5.3s) | ✓ (4 calls, 5.0s) |
| 11 | How many loans have problems — either currently running with debt or finished but not fully paid off? | ★ | ✓ (1 calls, 0.8s) | ✗ (1 calls, 0.9s) | ✓ (6 calls, 11.9s) | ✓ (7 calls, 11.2s) |
| 12 | How many loans were finished but the debt was not paid off? | ★ | ✗ (1 calls, 0.7s) | ✗ (1 calls, 0.8s) | ✗ (7 calls, 10.6s) | ✓ (7 calls, 10.6s) |
| 13 | How many credit card withdrawal transactions are there? | ★ | ✗ (1 calls, 0.9s) | ✓ (1 calls, 1.0s) | ✓ (6 calls, 6.7s) | ✓ (5 calls, 5.9s) |
| 14 | How many outgoing bank transfer transactions are there? | ★ | ✗ (1 calls, 0.7s) | ✓ (1 calls, 0.9s) | ✓ (5 calls, 6.7s) | ✓ (6 calls, 8.5s) |
| 15 | What is the total amount of loan repayment transactions? | ★ | ✗ (1 calls, 0.8s) | ✗ (1 calls, 0.8s) | ✓ (6 calls, 8.4s) | ✓ (6 calls, 8.6s) |
| 16 | How many accounts have ever been charged penalty interest? | ★ | ✗ (1 calls, 0.7s) | ✗ (1 calls, 1.1s) | ✓ (6 calls, 6.8s) | ✓ (8 calls, 9.7s) |
| 17 | How many transactions are pension income credits? | ★ | ✗ (1 calls, 0.6s) | ✓ (1 calls, 1.1s) | ✓ (7 calls, 8.5s) | ✓ (6 calls, 8.1s) |
| 18 | What is the average unemployment rate across districts in 1996? | ★ | ✗ (1 calls, 0.9s) | ✓ (1 calls, 0.8s) | ✓ (7 calls, 12.3s) | ✓ (8 calls, 11.3s) |
| 19 | What is the total population across all districts? | ★ | ✗ (1 calls, 0.7s) | ✓ (1 calls, 0.8s) | ✓ (5 calls, 5.5s) | ✓ (6 calls, 6.8s) |
| 20 | How many male clients are there? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.4s) | ✓ (4 calls, 4.1s) |

## Northwind (15 questions)

### Condition summary

| Condition | Accuracy | Avg latency | Avg LLM calls |
|---|---|---|---|
| Baseline 1-shot | 14/15 (93%) | 0.70s | 1.0 |
| Enriched 1-shot | 15/15 (100%) | 0.73s | 1.0 |
| Baseline tools | 15/15 (100%) | 5.11s | 4.5 |
| Enriched tools | 14/15 (93%) | 5.64s | 4.7 |

### Per-question results

| # | Question | Sensitive | Baseline 1-shot | Enriched 1-shot | Baseline tools | Enriched tools |
|---|---|---| --- | --- | --- | --- |
| 1 | How many customers are from Germany? |  | ✓ (1 calls, 0.5s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 4.4s) | ✓ (4 calls, 5.1s) |
| 2 | What is the average freight cost across all orders? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 4.3s) | ✓ (4 calls, 4.8s) |
| 3 | How many products are discontinued? |  | ✓ (1 calls, 0.7s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 3.6s) | ✓ (4 calls, 4.3s) |
| 4 | What is the most expensive product? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 3.7s) | ✓ (4 calls, 4.1s) |
| 5 | Which employee handled the most orders? Give their full name. |  | ✗ (1 calls, 0.8s) | ✓ (1 calls, 0.9s) | ✓ (5 calls, 5.4s) | ✓ (6 calls, 8.2s) |
| 6 | How many products are in the Beverages category? |  | ✓ (1 calls, 0.9s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.0s) | ✗ (5 calls, 5.5s) |
| 7 | How many suppliers are from the UK? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 3.8s) | ✓ (4 calls, 4.3s) |
| 8 | How many employees are based in London? |  | ✓ (1 calls, 0.7s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.3s) | ✓ (4 calls, 4.3s) |
| 9 | How many orders were shipped to France? |  | ✓ (1 calls, 0.5s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 4.5s) | ✓ (4 calls, 3.7s) |
| 10 | What is the average discount applied across all order lines? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 1.1s) | ✓ (4 calls, 3.8s) | ✓ (5 calls, 6.9s) |
| 11 | Which product appears in the most orders? |  | ✓ (1 calls, 1.1s) | ✓ (1 calls, 0.8s) | ✓ (9 calls, 15.2s) | ✓ (10 calls, 15.1s) |
| 12 | What is the total quantity of items sold across all orders? |  | ✓ (1 calls, 0.9s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 5.5s) | ✓ (4 calls, 3.9s) |
| 13 | How many suppliers are from Japan? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 4.5s) | ✓ (4 calls, 4.3s) |
| 14 | How many seafood products are there? |  | ✓ (1 calls, 0.8s) | ✓ (1 calls, 0.7s) | ✓ (5 calls, 5.6s) | ✓ (5 calls, 5.6s) |
| 15 | Which product has the most units in stock? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 4.1s) | ✓ (4 calls, 4.7s) |

## Notes

- **★ enrichment-sensitive**: questions where opaque columns or domain codes make the correct answer hard to reach without external hints.
- **Baseline 1-shot**: the LLM receives only column names and SQL types — no sample values, no semantic labels.
- **Enriched 1-shot**: the schema prompt includes `semantic_type` and up to 5 `examples` from Layer 1 deterministic enrichment (SemanticTypeInferencer).
- **Baseline tools**: the tool loop can call `get_sample` and `get_column_stats` to discover values at query time, but the registry is not available.
- **Enriched tools**: the tool loop additionally has `get_enriched_metadata` which returns pre-computed value_semantics and metadata from the registry.
- Layer 1 enrichment is fully deterministic (no LLM calls at enrichment time). Only querying incurs LLM cost.