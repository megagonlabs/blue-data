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

### Demo 0 — Data Quality Profiling (`data_quality_demo.py`)

**Story:** A vendor delivers a CRM export that looks structurally correct.
An AI agent queries it directly and gets an average salary 29× too high.
blue-data DQ profiling surfaces four concrete issues before any query runs —
an outlier row, 100% representation fragmentation on `country`, disguised
nulls in `email`, and a typo in `status`.  The corrected query returns the
right answer.

**Result:** 5 contacts / $2,056,999 → 7 contacts / $69,000 (29.8× correction)

```bash
python3 examples/scenario-demos/data_quality_demo.py
```

**Dataset:** synthetic 20-row CRM export | **API key:** not required | **[Sample output](scenario-demos/data_quality_demo.output.txt)**

---

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

### Data Quality Profiling Reference (`data_quality_demo.py`)

Developer reference for the full DQ pipeline.  Uses a synthetic `contacts`
table with deliberate errors to show every metric tier and where results land
in the registry.

**Tier 1 (always):** `missing_value_rate`, `fill_rate`, `is_partial_attribute`, `cardinality_ratio`

**Tier 2 (sample values + semantic type):** `disguised_missing_rate`, `format_violation_rate`, `heterogeneous_format_rate`, `embedded_value_rate`

**Tier 3 (frequencies + mean/variance):** `rare_value_rate`, `suspected_typo_rate`, `representation_fragmentation_rate`, `outlier_rate`

**Tier 4 (derived):** `repairability.{deterministic, ambiguous, unrecoverable}`, `misplaced_value_rate`

**Entity-level:** `effective_noise_rate`, `worst_attribute`, `rows_with_error_rate`, `multi_error_row_rate`

```bash
python3 examples/feature-demos/data_quality_demo.py
```

**API key:** not required | **[Sample output](feature-demos/data_quality_demo.output.txt)**

---

### Source-to-Source Data Export (`export_data_demo.py`)

Shows `registry.export_data` writing rows from a registered SQLiteDBSource to
CSV, JSON, and JSONL files — no manual pandas or SQL boilerplate. Demonstrates
format inference from extension and filtered export.

```bash
python3 examples/feature-demos/export_data_demo.py
```

**API key:** not required

---

### Source-to-Source Data Import (`import_data_demo.py`)

Shows `registry.import_data` moving rows between two registered sources. A
FileSource (CSV) is the origin; a SQLiteDBSource is the target. Demonstrates
`append` mode (incremental load) and `overwrite` mode (full reload).

```bash
python3 examples/feature-demos/import_data_demo.py
```

**API key:** not required | **[Sample output](feature-demos/import_data_demo.output.txt)**

---

### Natural Language Querying (`nl_query_demo.py`)

Shows `registry.execute_query_nl` — one call that translates a plain-English
question into SQL and executes it. The registry pulls the schema from its own
records and the LLM callable from the `metadata_enricher`. Demonstrates four
queries against a Northwind SQLite database.

```bash
pip install openai
export OPENAI_API_KEY=sk-...
python3 examples/feature-demos/nl_query_demo.py
```

**API key:** OpenAI required | **[Sample output](feature-demos/nl_query_demo.output.txt)**

---

### Tool-based NL Querying — SQL (`nl_tools_demo.py`)

Shows `execute_query_nl_tools` driving a multi-turn LLM tool loop against a
SQLite source. The LLM calls `list_databases`, `get_schema`, `execute_query`,
etc. in any order before returning a final answer. Contrast with `nl_query_demo.py`
which uses a single one-shot prompt.

```bash
pip install -e lib/ anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/nl_tools_demo.py
```

**API key:** Anthropic required

---

### Tool-based NL Querying — Graph (`nl_tools_graph_demo.py`)

Same tool-loop approach as `nl_tools_demo.py` but for a GraphSource. The LLM
uses purpose-built graph tools (`match_nodes`, `get_neighbors`, `match_edges`)
to traverse the graph naturally instead of constructing raw dict ops.

```bash
pip install -e lib/ anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 examples/feature-demos/nl_tools_graph_demo.py
```

**API key:** Anthropic required

---

### Programmatic Schema Creation (`schema_creation_demo.py`)

Shows how to declare a schema in the registry without syncing a live source.
Calls `create_source_database`, `create_source_database_collection`, and
`create_source_database_collection_entity` to define two tables, then inserts
rows and verifies they are queryable. Also shows idempotency (creating an
entity that already exists is a no-op).

```bash
python3 examples/feature-demos/schema_creation_demo.py
```

**API key:** not required | **[Sample output](feature-demos/schema_creation_demo.output.txt)**

---

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

## integration-demos/ — full pipeline on real datasets

End-to-end examples running the complete blue-data pipeline (register → sync →
enrich → search → query) against real datasets.

### Semantic Enrichment on a Multi-Table SQL Source (`sql_semantic_enrichment_demo.py`)

register → sync → enrich → search → query on the Northwind retail database.
Shows process semantics detection on `orders` (EVENT, event_time=order_date)
and executes multi-table SQL queries.

> Search results are BM25-only. Add a `VectorSource` + `embedding_fn` for
> full hybrid search.

```bash
python3 examples/integration-demos/sql_semantic_enrichment_demo.py
```

**Dataset:** Northwind (`data/northwind_sqlite.sql`) | **API key:** not required | **[Sample output](integration-demos/sql_semantic_enrichment_demo.output.txt)**

---

## framework-demos/ — framework integrations

### LangGraph — Direct Python API (`langgraph_direct_demo.py`)

3-node LangGraph pipeline using blue-data Python primitives directly:
`discover` (search_records) → `translate` (NL→SQL) → `execute` (run query).

```bash
pip install langgraph langchain-core langchain-openai
export OPENAI_API_KEY=sk-...
python3 examples/framework-demos/langgraph_direct_demo.py
```

**API key:** OpenAI required | **[Sample output](framework-demos/langgraph_direct_demo.output.txt)**

---

### LangGraph — MCP Integration (`langgraph_mcp_demo.py`)

ReAct agent that drives blue-data entirely through the MCP server. No
blue-data-specific imports on the agent side. MCP server launches automatically
as a subprocess — no separate terminal needed.

```bash
pip install langgraph langchain-core langchain-openai langchain-mcp-adapters
pip install -e lib/ -e platform/registry-mcp/
export OPENAI_API_KEY=sk-...
python3 examples/framework-demos/langgraph_mcp_demo.py
```

**API key:** OpenAI required | **[Sample output](framework-demos/langgraph_mcp_demo.output.txt)**

---

### LangGraph — REST API Integration (`langgraph_api_demo.py`)

3-node LangGraph pipeline that talks to blue-data exclusively over HTTP. No
blue-data Python imports on the agent side — only `httpx` calls to the running
REST API. The API server launches automatically as a subprocess.

```bash
pip install langgraph langchain-core langchain-openai httpx
pip install -e lib/ -e platform/api/
export OPENAI_API_KEY=sk-...
python3 examples/framework-demos/langgraph_api_demo.py
```

**API key:** OpenAI required | **[Sample output](framework-demos/langgraph_api_demo.output.txt)**

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

## Summary table

| File | Folder | API key | External | Output |
|------|--------|---------|----------|--------|
| `data_quality_demo.py` | scenario-demos | none | — | [output](scenario-demos/data_quality_demo.output.txt) |
| `coded_value_demo.py` | scenario-demos | Anthropic (SQL gen) | — | [output](scenario-demos/coded_value_demo.output.txt) |
| `description_search_demo.py` | scenario-demos | none at runtime | — | [output](scenario-demos/description_search_demo.output.txt) |
| `process_reasoning_demo.py` | scenario-demos | none (default) | — | [output](scenario-demos/process_reasoning_demo.output.txt) |
| `data_quality_demo.py` | feature-demos | none | — | [output](feature-demos/data_quality_demo.output.txt) |
| `export_data_demo.py` | feature-demos | none | — | — |
| `import_data_demo.py` | feature-demos | none | — | [output](feature-demos/import_data_demo.output.txt) |
| `nl_query_demo.py` | feature-demos | OpenAI | — | [output](feature-demos/nl_query_demo.output.txt) |
| `nl_tools_demo.py` | feature-demos | Anthropic | — | — |
| `nl_tools_graph_demo.py` | feature-demos | Anthropic | — | — |
| `schema_creation_demo.py` | feature-demos | none | — | [output](feature-demos/schema_creation_demo.output.txt) |
| `enrichment_demo.py` | feature-demos | Anthropic (optional) | — | [output](feature-demos/enrichment_demo.output.txt) |
| `sql_semantic_enrichment_demo.py` | integration-demos | none | — | [output](integration-demos/sql_semantic_enrichment_demo.output.txt) |
| `langgraph_direct_demo.py` | framework-demos | OpenAI | — | [output](framework-demos/langgraph_direct_demo.output.txt) |
| `langgraph_mcp_demo.py` | framework-demos | OpenAI | MCP server | [output](framework-demos/langgraph_mcp_demo.output.txt) |
| `langgraph_api_demo.py` | framework-demos | OpenAI | — | [output](framework-demos/langgraph_api_demo.output.txt) |
| `sqlite_example.py` | backends | none | — | — |
| `sqlite_data_registry_demo.py` | backends | none | — | [output](backends/sqlite_data_registry_demo.output.txt) |
| `registry_memory_example.py` | backends | none | — | [output](backends/registry_memory_example.output.txt) |
| `redis_demo.py` | backends | none | Redis Stack | [output](backends/redis_demo.output.txt) |
