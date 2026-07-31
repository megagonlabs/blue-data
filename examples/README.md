# blue-data Examples

This directory contains runnable examples organized by purpose.

## Quick start

All examples run from the repo root. Install the package first:

```bash
pip install -e lib/
```

---

## feature-demos/ — value proposition

Self-contained demos that each tell one clean story about what blue-data
enrichment does and why it matters. Designed for presentations.

### Demo 1 — Coded Value Disambiguation (`coded_value_demo.py`)

**Story:** SQL databases store values as domain-specific codes (PRIJEM, VYDAJ,
A/B/C/D). A baseline LLM guesses English equivalents and gets 0 rows.
blue-data Layer 1 auto-detects ENUM columns and captures the actual codes —
zero LLM enrichment cost.

**Result:** baseline 2/5 queries correct → enriched 5/5

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/coded_value_demo.py
```

**Dataset:** Czech banking (`data/finance_sqlite.sql`)
**API key:** required at runtime (for SQL generation only — enrichment is free)

---

### Demo 2 — Description-Enriched Data Discovery (`description_search_demo.py`)

**Story:** Column names like `freight`, `units_in_stock`, `title`, `order_date`
hide their meaning. Searching "shipping cost" or "current inventory" finds
nothing. blue-data Layer 2 generates descriptions once; the registry then
finds columns by semantic meaning.

**Result:** 1/4 queries found by name → 4/4 found after descriptions

```bash
# Descriptions are pre-generated and committed — no API key needed:
python3 examples/feature-demos/description_search_demo.py

# Regenerate descriptions (one-time, saves to data/northwind_descriptions.json):
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/description_search_demo.py --generate
```

**Dataset:** Northwind (`data/northwind_sqlite.sql`)
**API key:** not required at demo runtime (descriptions pre-generated)

---

### Demo 3 — Process Reasoning (`process_reasoning_demo.py`)

**Story:** LLMs treat event-log tables as static snapshots. "Current balance"
becomes AVG(balance). "Monthly trend" becomes a flat COUNT(*). blue-data
Layer 1 detects EVENT tables, identifies the event_time column, and flags
temporal reasoning constraints — zero LLM cost, zero annotation.

**Result:** 4 temporal failure modes shown, all fixed by Layer 1 enrichment

```bash
# Default: pre-built SQL examples, no API key needed:
python3 examples/feature-demos/process_reasoning_demo.py

# Live mode: generate SQL in real-time to verify enrichment changes output:
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/process_reasoning_demo.py --live
```

**Dataset:** Czech banking (`data/finance_sqlite.sql`)
**API key:** not required in default mode

---

## benchmarks/ — quantitative before/after

### NL2SQL Enrichment Benchmark (`enrichment_benchmark.py`)

Runs 15 NL2SQL questions through three conditions (no enrichment / Layer 1 /
Layer 2) and measures SQL correctness. Covers coded values, opaque column
names, process reasoning, and schema discovery.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/benchmarks/enrichment_benchmark.py
```

**Dataset:** Czech banking (`data/finance_sqlite.sql` + `data/finance_benchmark_queries.json`)
**API key:** required (generates and executes SQL)

---

### Finance Dataset Enrichment Demo (`finance_demo.py`)

Full enrichment walkthrough on the Czech banking dataset. Shows Layer 1
detection results (ENUM types, process semantics, event roles) and Layer 2
LLM-augmented enrichment (descriptions, SDI, DCM). Includes a before/after
NL2SQL comparison.

```bash
# Layer 1 only (no API key):
python3 examples/scenario-demos/finance_demo.py

# Layer 1 + Layer 2:
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/scenario-demos/finance_demo.py
```

**Dataset:** Czech banking (`data/finance_sqlite.sql`)
**API key:** optional (Layer 2 runs when key is present)

---

## scenario-demos/ — full end-to-end walkthroughs

### Northwind Pipeline (`northwind_demo.py`)

Walks the complete blue-data pipeline on the Northwind retail database:
register → sync → enrich → search → query. Shows process semantics detection
on the `orders` table (EVENT, event_time=order_date) and executes several
multi-table SQL queries.

> **Note:** Search results are BM25-only in this demo. Add a `VectorSource`
> with an `embedding_fn` to enable full hybrid BM25 + vector search.

```bash
python3 examples/scenario-demos/northwind_demo.py
```

**Dataset:** Northwind (`data/northwind_sqlite.sql`)
**API key:** not required

---

### Enrichment Pipeline Reference (`enrichment_demo.py`)

Developer-facing reference for the enrichment API. Uses a synthetic
`purchases` table to show every enrichment property produced by Layer 1
and Layer 2, including the `llm_fn` wiring contract. Also tests
idempotency: second pass with `rebuild=False` skips existing properties.

```bash
# Layer 1 only:
python3 examples/scenario-demos/enrichment_demo.py

# Layer 1 + Layer 2:
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/scenario-demos/enrichment_demo.py
```

**API key:** optional (Layer 2 skips gracefully when absent)

**Enrichment properties covered:**

| Property | What it captures |
|----------|-----------------|
| `value_semantics` | Semantic type: INTEGER, DATE, ENUM_CATEGORY, EMAIL, … |
| `semantic_discovery` | LLM-inferred domain subcategory and confidence |
| `domain_concept` | Canonical domain concept this attribute maps to |
| `interpretive_semantics` | Human-readable meaning of coded values |
| `value_axis` | Whether this attribute can serve as a quantitative axis |
| `quantitative_vst` | Role in quantitative analysis: MEASUREMENT, MAGNITUDE, … |
| `semantic_role` | Structural role: IDENTIFIER, EVENT_TIME, EVIDENCE, … |
| `process_vst_role` | Role in an event log: EVENT_MEASURE, EVENT_TIME, … |
| `semantic_links` | Detected statistical relationships between attribute pairs |
| `process_semantics` | EVENT table detection; which column is the time axis |
| `process_patterns` | Recurring patterns in the event sequence |
| `process_trends` | Trend signals over time |
| `conditional_value_distribution` | Value distribution conditioned on other attributes |

---

## integration-demos/ — framework integrations

### LangGraph — Direct Python API (`langgraph_direct_demo.py`)

A 3-node LangGraph pipeline that uses blue-data Python primitives directly:

```
discover → translate → execute
```

1. `discover` — `DataRegistry.search_records()` finds relevant columns
2. `translate` — `DataSource.translate_nl_to_native_query()` generates SQL
3. `execute` — `DataSource.execute_query()` runs the query and returns rows

```bash
pip install langgraph langchain-core langchain-openai
export OPENAI_API_KEY=sk-...
python3 examples/integration-demos/langgraph_direct_demo.py
```

**API key:** OpenAI key required

---

### LangGraph — MCP Integration (`langgraph_mcp_demo.py`)

A ReAct agent that drives blue-data entirely through the MCP server. No
blue-data-specific imports on the LangGraph side — the agent discovers
and calls tools from the running `registry-mcp` server automatically.

The MCP server is launched as a subprocess (stdio transport). No separate
terminal needed.

```bash
pip install langgraph langchain-core langchain-openai langchain-mcp-adapters
pip install -e lib/ -e platform/registry-mcp/
export OPENAI_API_KEY=sk-...
python3 examples/integration-demos/langgraph_mcp_demo.py
```

**API key:** OpenAI key required

---

## backends/ — infrastructure and API surface

These examples cover the full `DataRegistry` API and backend options. Start
here if you are integrating blue-data into a new application.

### Minimal SQLite quickstart (`sqlite_example.py`)

10-line example: register a SQLite source, sync it, run a query.

```bash
python3 examples/backends/sqlite_example.py
```

---

### SQLite DataRegistry full pipeline (`sqlite_data_registry_demo.py`)

Covers every major `DataRegistry` operation in sequence:
register → sync → stats → enrich → relations → reconnect → serialize →
multi-source → search. The reference example for new integrations.

```bash
python3 examples/backends/sqlite_data_registry_demo.py
```

---

### In-memory Registry API (`registry_memory_example.py`)

Covers the full `Registry` public API using only in-memory backends (no
database, no Redis). Shows CRUD, scoped listing, property filtering,
serialization round-trips, the `rebuild` flag, hybrid search, and
keyword-only search fallback.

```bash
python3 examples/backends/registry_memory_example.py
```

---

### Redis-backed Registry (`redis_demo.py`)

Production backend demo using Redis Stack (`RedisJSONSource` + `RedisVectorSource`).
Covers namespace isolation, hybrid BM25 + vector search, serialization,
and cleanup. Falls back to SQLite if Postgres is unavailable.

**Prerequisites:** Redis Stack running on `localhost:6379`

```bash
redis-stack-server &   # or: docker run -p 6379:6379 redis/redis-stack
python3 examples/backends/redis_demo.py
```

---

## Other

### Claude Desktop Walkthrough (`claude_desktop_walkthrough.md`)

Step-by-step guide for using blue-data through the Claude Desktop MCP
integration. No code — follow the instructions in the document.

---

## Summary table

| File | Group | API key | External services |
|------|-------|---------|-------------------|
| `coded_value_demo.py` | demo | Anthropic (SQL gen) | — |
| `description_search_demo.py` | demo | none at runtime | — |
| `process_reasoning_demo.py` | demo | none (default mode) | — |
| `enrichment_benchmark.py` | benchmark | Anthropic | — |
| `finance_demo.py` | benchmark | Anthropic (optional) | — |
| `northwind_demo.py` | pipeline | none | — |
| `enrichment_demo.py` | pipeline | Anthropic (optional) | — |
| `langgraph_direct_demo.py` | integration | OpenAI | — |
| `langgraph_mcp_demo.py` | integration | OpenAI | MCP server |
| `sqlite_example.py` | backend | none | — |
| `sqlite_data_registry_demo.py` | backend | none | — |
| `registry_memory_example.py` | backend | none | — |
| `redis_demo.py` | backend | none | Redis Stack |
