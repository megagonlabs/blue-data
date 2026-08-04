# blue-data Examples

This directory contains runnable examples organized by purpose.

## Quick start

```bash
pip install -e lib/
```

---

## scenario-demos/ — value proposition demos

Each demo tells one clean story with a quantitative before/after result.
Designed for presentations. Start here.

### Demo 1 — Coded Value Disambiguation (`coded_value_demo.py`)

**Story:** SQL databases store values as domain codes (PRIJEM, VYDAJ, A/B/C/D).
A baseline LLM guesses English equivalents and gets 0 rows. blue-data Layer 1
auto-detects ENUM columns and captures the actual codes — zero LLM cost.

**Result:** baseline 2/5 → enriched 5/5

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/scenario-demos/coded_value_demo.py
```

**Dataset:** Czech banking (`data/finance_sqlite.sql`) | **API key:** required (SQL generation only) | **[Sample output](scenario-demos/coded_value_demo.output.txt)**

---

### Demo 2 — Description-Enriched Data Discovery (`description_search_demo.py`)

**Story:** Column names like `freight`, `units_in_stock`, `title`, `order_date`
hide their meaning. Searching "shipping cost" or "current inventory" finds
nothing. blue-data Layer 2 generates descriptions once; the registry then
finds columns by semantic meaning.

**Result:** 1/4 → 4/4 queries resolved

```bash
# Zero API key — descriptions pre-generated and committed:
python3 examples/scenario-demos/description_search_demo.py

# Regenerate descriptions (one-time):
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/scenario-demos/description_search_demo.py --generate
```

**Dataset:** Northwind (`data/northwind_sqlite.sql`) | **API key:** not required at runtime | **[Sample output](scenario-demos/description_search_demo.output.txt)**

---

### Demo 3 — Process Reasoning (`process_reasoning_demo.py`)

**Story:** LLMs treat event-log tables as static snapshots. "Current balance"
becomes AVG(balance). "Monthly trend" becomes flat COUNT(*). blue-data Layer 1
detects EVENT tables, identifies event_time, and flags temporal constraints —
zero LLM cost, zero annotation.

**Result:** 4 temporal failure modes shown, all fixed by Layer 1

```bash
# Pre-built examples, no API key:
python3 examples/scenario-demos/process_reasoning_demo.py

# Live SQL generation to verify enrichment changes output:
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/scenario-demos/process_reasoning_demo.py --live
```

**Dataset:** Czech banking (`data/finance_sqlite.sql`) | **API key:** not required (default mode) | **[Sample output](scenario-demos/process_reasoning_demo.output.txt)**

---

## feature-demos/ — how specific features work

Deep-dives into individual blue-data features. No before/after story — shows
what a feature does, what it produces, and how to wire it up.

### Enrichment Pipeline Reference (`enrichment_demo.py`)

Developer reference for wiring up and running the enrichment pipeline. Uses a
synthetic `purchases` table to show what each layer infers and where the results
land in the registry.

**Layer 1 (no API key):** runs `SemanticTypeInferencer` on sample values, then
infers semantic roles (`id` → IDENTIFIER, `purchase_date` → EVENT_TIME,
`amount` → EVIDENCE, `category` → SEGMENTATION_DRIVER), detects the table as an
EVENT log, and finds cross-column links (`category` SEGMENTS `amount`).

**Layer 2 (API key optional):** calls an LLM per column for VSI (richer semantic
type) and SDI (domain subcategory label such as `TRANSACTION_AMOUNT`). Shows the
`llm_fn` wiring contract and demonstrates that `rebuild=False` makes the second
pass a no-op (0 additional LLM calls).

```bash
# Layer 1 only:
python3 examples/feature-demos/enrichment_demo.py

# Layer 1 + Layer 2:
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/enrichment_demo.py
```

**API key:** optional (Layer 2 skips gracefully when absent) | **[Sample output](feature-demos/enrichment_demo.output.txt)**

---

## pipeline-demos/ — full pipeline on real datasets

End-to-end examples running the complete blue-data pipeline (register → sync →
enrich → search → query) against real datasets.

### Semantic Enrichment on a Multi-Table SQL Source (`sql_semantic_enrichment_demo.py`)

register → sync → enrich → search → query on the Northwind retail database.
Shows process semantics detection on `orders` (EVENT, event_time=order_date)
and executes multi-table SQL queries.

> Search results are BM25-only. Add a `VectorSource` + `embedding_fn` for
> full hybrid search.

```bash
python3 examples/pipeline-demos/sql_semantic_enrichment_demo.py
```

**Dataset:** Northwind (`data/northwind_sqlite.sql`) | **API key:** not required | **[Sample output](pipeline-demos/sql_semantic_enrichment_demo.output.txt)**

---

## integration-demos/ — framework integrations

### LangGraph — Direct Python API (`langgraph_direct_demo.py`)

3-node LangGraph pipeline using blue-data Python primitives directly:
`discover` (search_records) → `translate` (NL→SQL) → `execute` (run query).

```bash
pip install langgraph langchain-core langchain-openai
export OPENAI_API_KEY=sk-...
python3 examples/integration-demos/langgraph_direct_demo.py
```

**API key:** OpenAI required | **[Sample output](integration-demos/langgraph_direct_demo.output.txt)**

---

### LangGraph — MCP Integration (`langgraph_mcp_demo.py`)

ReAct agent that drives blue-data entirely through the MCP server. No
blue-data-specific imports on the agent side. MCP server launches automatically
as a subprocess — no separate terminal needed.

```bash
pip install langgraph langchain-core langchain-openai langchain-mcp-adapters
pip install -e lib/ -e platform/registry-mcp/
export OPENAI_API_KEY=sk-...
python3 examples/integration-demos/langgraph_mcp_demo.py
```

**API key:** OpenAI required | **[Sample output](integration-demos/langgraph_mcp_demo.output.txt)**

---

### LangGraph — REST API Integration (`langgraph_api_demo.py`)

3-node LangGraph pipeline that talks to blue-data exclusively over HTTP. No
blue-data Python imports on the agent side — only `httpx` calls to the running
REST API. The API server launches automatically as a subprocess.

```bash
pip install langgraph langchain-core langchain-openai httpx
pip install -e lib/ -e platform/api/
export OPENAI_API_KEY=sk-...
python3 examples/integration-demos/langgraph_api_demo.py
```

**API key:** OpenAI required | **[Sample output](integration-demos/langgraph_api_demo.output.txt)**

---

## backends/ — infrastructure and storage backends

Start here when integrating blue-data into a new application.

### Minimal SQLite quickstart (`sqlite_example.py`)

10-line example: register a source, sync, query.

```bash
python3 examples/backends/sqlite_example.py
```

### SQLite DataRegistry full pipeline (`sqlite_data_registry_demo.py`)

Every major `DataRegistry` operation: register → sync → stats → enrich →
relations → reconnect → serialize → multi-source → search.

```bash
python3 examples/backends/sqlite_data_registry_demo.py
```

**[Sample output](backends/sqlite_data_registry_demo.output.txt)**

### In-memory Registry API (`registry_memory_example.py`)

Full `Registry` public API with in-memory backends. No database or Redis
needed. Covers CRUD, scoped listing, property filtering, serialization,
the `rebuild` flag, hybrid search, and keyword-only fallback.

```bash
python3 examples/backends/registry_memory_example.py
```

**[Sample output](backends/registry_memory_example.output.txt)**

### Redis-backed Registry (`redis_demo.py`)

Production backend: `RedisJSONSource` + `RedisVectorSource`. Covers namespace
isolation, hybrid BM25 + vector search, serialization, and cleanup.

```bash
redis-stack-server &   # or: docker run -p 6379:6379 redis/redis-stack
python3 examples/backends/redis_demo.py
```

**Requires:** Redis Stack on `localhost:6379` | **[Sample output](backends/redis_demo.output.txt)**

---

## benchmarks/

### NL2SQL Enrichment Benchmark (`enrichment_benchmark.py`)

Measures semantic correctness improvement from blue-data enrichment on the Czech
banking dataset. **24 questions across 7 categories**, each targeting a distinct
enrichment feature. Observed result: **17% → 71% semantic correctness**
at zero LLM enrichment cost.

- **none** (4): control questions answerable from column names alone — both conditions expected correct.
- **enum_coded_value** (6): Czech domain codes (`VKLAD`, `POJISTNE`, `SIPO`, `PREVOD NA UCET`…)
  that Haiku cannot guess from English. Enrichment injects ENUM_CATEGORY values; baseline
  generates English words and gets 0 rows.
- **opaque_column** (3): `district` columns `a2`–`a16` have no meaningful names.
  Enrichment injects `a3` as ENUM_CATEGORY with actual region names (`Prague`, `central Bohemia`…)
  and `a2` as district name samples — baseline confuses the two columns.
- **current_state** (3): `trans.balance` is a running total per event; "current balance"
  is the latest row per account, not `AVG`. Enrichment provides `latest_record_only:
  partition_by=[account_id]` and marks `balance` as `STATE_VARIABLE`.
- **distributional** (3): Enrichment computes `value_axis` statistical extremes
  (`amount > 21200` = large outlier, `balance < 9500` = critically low). Baseline
  picks arbitrary round thresholds; enrichment uses the actual data-derived cutoffs.
- **quantitative_misinterpretation** (3): ratio and net-credit queries requiring correct
  `PRIJEM`/`VYDAJ` ENUM codes to isolate the right population — baseline gets 0 rows.
- **time_grain** (2): ENUM-filtered monthly aggregations (`type='PRIJEM'`) using
  `time_grains=['monthly']` and `AGGREGATE_OVER_TIME` operator hint from enrichment.
  Baseline fails on both the ENUM code and the time bucket simultaneously.

See **[RESULTS.md](benchmarks/RESULTS.md)** for the latest run: charts, per-question verdicts, and category breakdowns.

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# baseline vs enriched, with LLM judge (recommended)
python3 examples/benchmarks/enrichment_benchmark.py --judge --model claude-haiku-4-5-20251001

# write a markdown report with Mermaid charts to benchmarks/RESULTS.md
python3 examples/benchmarks/enrichment_benchmark.py --judge --model claude-haiku-4-5-20251001 --report

# also run enriched+L2 (LLM-augmented enrichment)
python3 examples/benchmarks/enrichment_benchmark.py --judge --layer2 --model claude-haiku-4-5-20251001

# save raw JSON results
python3 examples/benchmarks/enrichment_benchmark.py --judge --out results/run.json --model claude-haiku-4-5-20251001
```

---

## Summary table

| File | Folder | API key | External | Output |
|------|--------|---------|----------|--------|
| `coded_value_demo.py` | scenario-demos | Anthropic (SQL gen) | — | [output](scenario-demos/coded_value_demo.output.txt) |
| `description_search_demo.py` | scenario-demos | none at runtime | — | [output](scenario-demos/description_search_demo.output.txt) |
| `process_reasoning_demo.py` | scenario-demos | none (default) | — | [output](scenario-demos/process_reasoning_demo.output.txt) |
| `enrichment_demo.py` | feature-demos | Anthropic (optional) | — | [output](feature-demos/enrichment_demo.output.txt) |
| `sql_semantic_enrichment_demo.py` | pipeline-demos | none | — | [output](pipeline-demos/sql_semantic_enrichment_demo.output.txt) |
| `langgraph_direct_demo.py` | integration-demos | OpenAI | — | [output](integration-demos/langgraph_direct_demo.output.txt) |
| `langgraph_mcp_demo.py` | integration-demos | OpenAI | MCP server | [output](integration-demos/langgraph_mcp_demo.output.txt) |
| `langgraph_api_demo.py` | integration-demos | OpenAI | — | [output](integration-demos/langgraph_api_demo.output.txt) |
| `sqlite_example.py` | backends | none | — | — |
| `sqlite_data_registry_demo.py` | backends | none | — | [output](backends/sqlite_data_registry_demo.output.txt) |
| `registry_memory_example.py` | backends | none | — | [output](backends/registry_memory_example.output.txt) |
| `redis_demo.py` | backends | none | Redis Stack | [output](backends/redis_demo.output.txt) |
| `enrichment_benchmark.py` | benchmarks | Anthropic | — | — |
