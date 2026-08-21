# NL2Q Enrichment Benchmark — 2×2 Matrix

Model: `claude-haiku-4-5-20251001`  |  Total questions: 10

## Conditions

| Label | Description |
|---|---|
| Baseline 1-shot | Raw schema injected into a single prompt; no enrichment |
| Enriched 1-shot | Enriched schema with semantic types and sample values injected |
| Baseline tools  | Tool loop (list, get_schema, execute_query); no enrichment |
| Enriched tools  | Tool loop + `get_enriched_metadata` registry tool available |

## Finance (10 questions)

### Condition summary

| Condition | Accuracy | Avg latency | Avg LLM calls |
|---|---|---|---|
| Baseline 1-shot | 7/10 (70%) | 1.53s | 1.0 |
| Enriched 1-shot | 9/10 (90%) | 0.97s | 1.0 |
| Baseline tools | 10/10 (100%) | 7.42s | 4.8 |
| Enriched tools | 10/10 (100%) | 7.04s | 4.8 |

### Enrichment-sensitive questions (4 of 10)

| Condition | Accuracy |
|---|---|
| Baseline 1-shot | 1/4 (25%) |
| Enriched 1-shot | 3/4 (75%) |
| Baseline tools | 4/4 (100%) |
| Enriched tools | 4/4 (100%) |

### Per-question results

| # | Question | Sensitive | Baseline 1-shot | Enriched 1-shot | Baseline tools | Enriched tools |
|---|---|---| --- | --- | --- | --- |
| 1 | How many female clients are there? |  | ✓ (1 calls, 0.9s) | ✓ (1 calls, 0.7s) | ✓ (4 calls, 4.8s) | ✓ (4 calls, 4.6s) |
| 2 | What is the average loan amount? |  | ✓ (1 calls, 0.7s) | ✓ (1 calls, 2.5s) | ✓ (4 calls, 5.6s) | ✓ (4 calls, 4.3s) |
| 3 | Which district has the highest average salary? | ★ | ✗ (1 calls, 0.8s) | ✓ (1 calls, 0.9s) | ✓ (7 calls, 8.9s) | ✓ (6 calls, 9.9s) |
| 4 | How many loans are currently running with no problems? | ★ | ✗ (1 calls, 0.6s) | ✗ (1 calls, 0.7s) | ✓ (6 calls, 14.0s) | ✓ (6 calls, 9.8s) |
| 5 | What is the total amount of all credit (incoming) transactions? | ★ | ✓ (1 calls, 0.7s) | ✓ (1 calls, 0.8s) | ✓ (5 calls, 8.0s) | ✓ (5 calls, 10.6s) |
| 6 | How many accounts have a monthly statement frequency? | ★ | ✗ (1 calls, 8.1s) | ✓ (1 calls, 1.2s) | ✓ (6 calls, 9.6s) | ✓ (6 calls, 10.3s) |
| 7 | What is the average loan duration in months? |  | ✓ (1 calls, 0.6s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 3.9s) | ✓ (5 calls, 6.0s) |
| 8 | How many accounts have at least one loan? |  | ✓ (1 calls, 0.9s) | ✓ (1 calls, 0.6s) | ✓ (4 calls, 10.5s) | ✓ (4 calls, 4.8s) |
| 9 | What is the largest single transaction amount? |  | ✓ (1 calls, 1.2s) | ✓ (1 calls, 0.8s) | ✓ (4 calls, 4.3s) | ✓ (4 calls, 4.5s) |
| 10 | How many accounts have no transactions at all? |  | ✓ (1 calls, 0.7s) | ✓ (1 calls, 1.0s) | ✓ (4 calls, 4.6s) | ✓ (4 calls, 5.5s) |

## Notes

- **★ enrichment-sensitive**: questions where opaque columns or domain codes make the correct answer hard to reach without external hints.
- **Baseline 1-shot**: the LLM receives only column names and SQL types — no sample values, no semantic labels.
- **Enriched 1-shot**: the schema prompt includes `semantic_type` and up to 5 `examples` from Layer 1 deterministic enrichment (SemanticTypeInferencer).
- **Baseline tools**: the tool loop can call `get_sample` and `get_column_stats` to discover values at query time, but the registry is not available.
- **Enriched tools**: the tool loop additionally has `get_enriched_metadata` which returns pre-computed value_semantics and metadata from the registry.
- Layer 1 enrichment is fully deterministic (no LLM calls at enrichment time). Only querying incurs LLM cost.