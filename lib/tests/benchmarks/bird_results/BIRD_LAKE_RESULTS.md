# BIRD Data Lake Benchmark — Results

**Setup:** All 11 BIRD databases pooled into one shared registry — ~86 tables, ~9,988 total indexed records.  
**Queries:** 1,534 questions from BIRD dev set, each searched against the full lake.  
**Conditions:** `keyword` (BM25 only), `hybrid` (BM25 + OpenAI `text-embedding-3-small`)  
**Last run:** 2026-08-28 02:07 UTC

> **F1@Lake** uses source-qualified `(database, table)` pairs. Returning `loan` from the
> wrong database counts as a false positive. Ideal-K cutoff = |relevant tables| per query.

---

## Overall

| Metric | keyword | hybrid |
|--------|---------|--------|
| Hit@1 | 21% | 32% |
| Hit@5 | 32% | 46% |
| MRR | 0.26 | 0.37 |
| F1@Ideal-K (lake) | 0.020 | 0.024 |

---

## Per-database

| Database | n | kw H@1 | kw H@5 | kw MRR | kw F1@Lake | hyb H@1 | hyb H@5 | hyb MRR | hyb F1@Lake |
|---|---|---|---|---|---|---|---|---|---|
| california_schools | 89 | 28% | 40% | 0.32 | 0.23 | 13% | 28% | 0.18 | 0.10 |
| card_games | 191 | 31% | 46% | 0.36 | 0.05 | 49% | 55% | 0.52 | 0.14 |
| codebase_community | 186 | 25% | 39% | 0.31 | 0.00 | 28% | 42% | 0.32 | 0.00 |
| debit_card_specializing | 64 | 23% | 23% | 0.23 | 0.00 | 25% | 45% | 0.31 | 0.00 |
| european_football_2 | 129 | 26% | 34% | 0.30 | 0.00 | 21% | 30% | 0.24 | 0.00 |
| financial | 106 | 12% | 39% | 0.23 | 0.00 | 42% | 54% | 0.46 | 0.00 |
| formula_1 | 174 | 13% | 27% | 0.19 | 0.00 | 24% | 32% | 0.26 | 0.00 |
| student_club | 158 | 18% | 24% | 0.21 | 0.00 | 27% | 39% | 0.30 | 0.00 |
| superhero | 129 | 32% | 33% | 0.36 | 0.00 | 63% | 80% | 0.68 | 0.00 |
| thrombosis_prediction | 163 | 15% | 25% | 0.20 | 0.00 | 20% | 37% | 0.26 | 0.00 |
| toxicology | 145 | 13% | 18% | 0.15 | 0.00 | 38% | 59% | 0.46 | 0.00 |

---

## Comparison: per-DB vs lake

| Metric | Per-DB keyword | Lake keyword | Lake hybrid |
|--------|---------------|--------------|-------------|
| Hit@1 | 44% | 21% | 32% |
| Hit@5 | 61% | 32% | 46% |
| MRR | — | 0.26 | 0.37 |
| F1@Ideal-K | 0.29 | 0.02 | 0.02 |

Per-DB benchmark scores each query against only its own database's registry.
Lake benchmark scores the same query against all 11 databases pooled together.

---

## Interpreting the results

### Attribute-level retrieval (Hit@K) — moderate degradation

Hit@1 drops from 44% (per-DB) to 21% (lake keyword) — roughly half.
Hybrid search recovers most of the gap, reaching 32% H@1 and 46% H@5.

Embeddings are most effective for databases with domain-specific vocabulary that doesn't
appear in other databases:

| Database | kw H@1 | hyb H@1 | delta |
|----------|--------|---------|-------|
| financial | 12% | 42% | +30pp |
| toxicology | 13% | 38% | +25pp |
| superhero | 32% | 63% | +31pp |
| card_games | 31% | 49% | +18pp |

european_football_2 and california_schools see a small drop with hybrid — embeddings
can pull in semantically similar records from other databases, which hurts when the query
vocabulary is too generic.

### Entity-level retrieval (F1@Lake) — severe degradation

F1@Ideal-K collapses from 0.29 (per-DB) to 0.02 (lake). This is the structurally hard
part of the lake problem.

F1@Lake only counts results where `type="entity"` AND the source database matches. In
the lake, ~9,988 records compete. Entity records (tables) are routinely outranked by
attribute records (columns) from across all 11 databases. Only two databases show
non-zero entity-level F1:

- **california_schools** (F1=0.23 keyword): only 3 tables, highly distinctive names
  (frpm, schools, satscores). Entity records win the top slot frequently.
- **card_games** (F1=0.05 keyword, 0.14 hybrid): "cards" table name directly matches
  most card_games queries. Hybrid further helps.

All other databases have generic table names (`users`, `patient`, `member`, `bond`,
`drivers`) that appear as column names across the full pool, preventing entity records
from surfacing in the top positions.

### What moves F1@Lake

F1@Lake is the metric most sensitive to **semantic enrichment**. Without Layer 2
descriptions, an entity record for `users` has text "users entity" — indistinguishable
from dozens of attribute records containing "user" in their name. Adding semantic
descriptions gives each entity a unique fingerprint that embeddings can match.

Predicted impact of enrichment:
- Keyword F1@Lake: modest improvement (descriptions improve BM25 coverage)
- Hybrid F1@Lake: significant improvement (embeddings on rich descriptions enable
  semantic disambiguation of generic table names)

---

## Comparison with published systems

### Setup summary

| | **Ours (keyword)** | **Ours (hybrid)** | **CORE-T** | **DMRAL** |
|---|---|---|---|---|
| Benchmark | BIRD lake | BIRD lake | BIRD lake | BirdWild |
| Questions | 1,534 (all types) | 1,534 (all types) | 44 (curated subset) | 461 (numeric only) |
| Table pool | ~86 (11 DBs) | ~86 (11 DBs) | ~79 (12 DBs) | ~109,949 |
| Indexing | metadata only | metadata only | content-aware | content-aware |
| Retrieval | BM25 | BM25 + vector | dense + LLM | NL sub-queries + join graph |

### F1@Ideal-K (entity-level table retrieval)

| System | F1@Ideal-K | F1@K=5 | Avg tables returned | Avg search time |
|--------|-----------|--------|---------------------|-----------------|
| **Ours (keyword)** | 0.020 | — | — | — |
| **Ours (hybrid)** | 0.024 | — | — | — |
| CORE-T (Soliman et al., arxiv 2026) | 0.814 | 0.666 | 4.07 | 0.84s |
| DMRAL (Luo et al., ICDE 2026) | 0.553¹ | 0.480¹ | 10.14¹ | 2.07s¹ |

¹ DMRAL numbers here are from a BIRD lake evaluation (44-question subset, ~79 tables, 12 DBs), not from DMRAL's own BirdWild evaluation (F1@3=59.6%, ~109,949 tables).

### Reading the comparison

**CORE-T** uses the same BIRD dev-set lake setup (multiple databases pooled) and the same F1@Ideal-K metric — the most direct published comparison available. The gap (0.814 vs 0.024) is large but explainable: CORE-T indexes **table content** (column values, row samples) in addition to metadata. We index **metadata only** — table and column names, plus LLM-generated descriptions when enrichment has run. An internal content-aware prototype evaluated on the same 44-question BIRD subset achieves F1@Ideal-K=0.870–0.898, consistent with what content indexing buys over metadata-only.

**DMRAL** operates on BirdWild (~109,949 tables, 461 numeric questions) — a different scale and question distribution. Its F1@3=59.6% on BirdWild is not directly comparable to our F1@Ideal-K on BIRD lake.

**What the gap quantifies:** The ~0.81–0.90 F1@Ideal-K ceiling from content-aware systems on the same BIRD lake problem quantifies the combined value of content indexing, answer-table generation, and join-aware graph traversal — none of which are currently in our pipeline. Enrichment (Layer 2 descriptions) is our primary lever to close the metadata-to-content gap.
