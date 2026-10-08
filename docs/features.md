# Features

## Overview

blue-data is a data intelligence layer for AI applications. It provides a unified interface to register, introspect, and query heterogeneous data sources such as SQL databases, document stores, and graph databases — and enriches them with semantic metadata that makes data understandable to AI agents and language models. It sits between raw data and the AI layer, answering questions like: what data exists, what it means, how it relates, and how it can safely be queried.

Its core capabilities include:

- **Unified access** across heterogeneous enterprise data sources
- **Deep data discoverability** to identify the most relevant data for a given task
- **Fine-grained semantic understanding** of schemas, tables, columns, relationships, business semantics, and values
- **Task-aware intelligence** to determine whether available data is sufficient and appropriate to accomplish a specific task
- **Cross-source intelligence** that understands relationships and semantics across multiple enterprise systems
- **AI-ready semantic metadata** that enables more accurate reasoning, planning, and decision-making over enterprise data

## Unified data source interface

Consistent API across heterogeneous backends. Register once, query uniformly.

- **SQL** — SQLite, PostgreSQL, MySQL
- **Document** — MongoDB
- **Graph** — Neo4j
- **File** — CSV, JSON, JSONL, Parquet (directory of files as a source)
- **Vector** — MemoryVectorSource, RedisVectorSource, ChromaDB
- **Stream** — Redis Streams, MemoryStreamSource
- **Network** — BayesianNetworkSource (probabilistic graphical models via pgmpy)

Consistent operations across all: list databases / collections / entities, execute queries, collect stats, introspect schema.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry()

source = SQLiteDBSource(
    name="sqlite",
    properties={
        "connection": {"database_directory": "/tmp/my-data"}
    },
)
registry.register_source(source)

# Create a database and table
source.create_database("mydb")
registry.execute_query(
    source="sqlite",
    database="mydb",
    query="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
    optional_properties={"commit": True},
)

# List what the source contains
print(registry.list_source_databases("sqlite"))
print(registry.list_database_collections("sqlite", "mydb"))
print(registry.list_collection_entities("sqlite", "mydb", "public"))
```

---

## Data registry

A live catalog that mirrors source structure as addressable, searchable records.

- **Hierarchical structure** — databases → collections → entities → attributes
- Each record carries description, properties, statistics, and enriched metadata
- Sync from live sources on demand — incremental or recursive
- Stats collection at every level: row counts, value distributions, sample data

```python
# Sync source structure into the registry
registry.sync_source("sqlite", recursive=True)

# Collect stats at every level
registry.collect_source_database_stats("sqlite", "mydb")
registry.collect_source_database_collection_stats("sqlite", "mydb", "public")
registry.collect_source_database_collection_entity_stats("sqlite", "mydb", "public", "users")
registry.collect_source_database_collection_entity_attribute_stats(
    "sqlite", "mydb", "public", "users", "name"
)
```

---

## Semantic enrichment

Automatically infers meaning from data. No LLM required.

- **Semantic type inference** — detects dates, currencies, identifiers, categories, free text, and more
- **Attribute roles** — classifies each column by its functional role (identifier, time dimension, grouping attribute, measurement)
- **Value axes** — magnitude and ordinal ranges from distributions
- **Process semantics** — detects event tables, temporal cadence, trend direction
- **Quantitative rules** — total/component relationships, safe aggregation guidance, derived metric candidates
- **Semantic links** — statistically validated relationships between attributes

```python
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

# Deterministic-only — no API key needed
enricher = MetaData(llm_fn=None)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)

# Prerequisites must be run in order
registry.sync_all(recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
```

See `examples/feature-demos/enrichment_demo.py` for a deep-dive including standalone `SemanticTypeInferencer` usage, idempotency, and rebuild behavior.

---

## LLM-augmented metadata

When paired with an LLM (Anthropic, OpenAI, or any provider), generates natural-language descriptions, domain concept mappings, and interpretive semantics.

```python
import anthropic
from blue_data.registry.enrichment.metadata import MetaData

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def llm_fn(prompt: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""

enricher = MetaData(llm_fn=llm_fn)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)
```

`llm_fn` is provider-agnostic — any `(str) -> str` callable works. `rebuild=False` (default) is idempotent: existing properties are not overwritten on subsequent calls.

---

## Data quality profiling

Measures data reliability at the attribute and entity level from already-collected stats — no LLM required. Results are stored as registry properties and are available to agents before any query runs.

- **Tier 1 — raw counts** — `missing_value_rate`, `fill_rate`, `is_partial_attribute`, `cardinality_ratio`
- **Tier 2 — format and sentinel checks** — `disguised_missing_rate` (sentinel vocabulary: "N/A", "null", "unknown", …), `format_violation_rate` (EMAIL, DATE, UUID, …), `heterogeneous_format_rate` (mixed date styles), `embedded_value_rate`
- **Tier 3 — frequency-based** — `rare_value_rate`, `suspected_typo_rate` (edit-distance ≤ 2 from frequent values), `representation_fragmentation_rate` ("UK" ↔ "United Kingdom"), `outlier_rate` (z-score, weighted by frequency)
- **Tier 4 — derived** — `repairability.{deterministic, ambiguous, unrecoverable}` (no extra data needed), `misplaced_value_rate` (cross-column)
- **Entity-level summary** — `effective_noise_rate`, `worst_attribute`, `dominant_error_type`, `rows_with_error_rate`, `multi_error_row_rate`, `duplicate_row_rate`

Tier 2 format checks work best after enrichment (semantic type determines which format pattern to apply). Tiers 1, 3, and 4 are always available from stats alone.

```python
# Prerequisites: sync and collect_stats must run first
registry.sync_all(recursive=True)
registry.collect_source_stats("mydb", recursive=True)

# Optional: enrichment sharpens Tier 2 format checks (no LLM needed)
registry.enrich_source("mydb")

# Compute and store DQ metrics across the full source hierarchy
registry.compute_source_data_quality("mydb")

# Read per-attribute metrics
dq = registry.get_source_database_collection_entity_attribute_property(
    "mydb", "sales", "public", "orders", "email", "data_quality"
)
print(dq["missing_value_rate"])          # 0.05
print(dq["disguised_missing_rate"])      # 0.20  ("N/A", "NONE", …)
print(dq["format_violation_rate"])       # 0.30  (not matching EMAIL pattern)
print(dq["representation_fragmentation_rate"])  # 1.0  ("US" ↔ "United States")
print(dq["repairability"])               # {"deterministic": 0.42, "ambiguous": 0.06, "unrecoverable": 0.05}

# Read entity-level summary
summary = registry.get_source_database_collection_entity_property(
    "mydb", "sales", "public", "orders", "data_quality_summary"
)
print(summary["worst_attribute"])        # "email"
print(summary["rows_with_error_rate"])   # 0.5
```

See `examples/feature-demos/data_quality_demo.py` for a tier-by-tier reference, and `examples/scenario-demos/data_quality_demo.py` for a before/after story showing a 29.8× query correction driven by DQ findings.

---

## Hybrid search

BM25 keyword + vector similarity search over all registry records, with hierarchical score propagation.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=my_embedding_fn,   # callable: str → list[float]
    vector_dim=1536,
    rebuild=True,
)

results = registry.search_records("user accounts")
for r in results:
    print(r["name"], r.get("_score"))
```

Omit `vector_source` and `embedding_fn` to fall back to keyword-only search. Search weights and thresholds are tunable — see the [Configuration](../README.md#configuration) section.

---

## Natural language querying

Two complementary modes for translating natural language questions into native queries.

### One-shot (`execute_query_nl`)

Translates a question into a native query in a single LLM call, using schema context from the registry. Supported dialects: SQL (SQLite, PostgreSQL, MySQL), Cypher (Neo4j), MongoDB filters. Vector sources embed the query and run KNN — no LLM required.

**SQL and graph sources** — schema context from the registry is automatically injected into the LLM prompt:

```python
rows = registry.execute_query_nl(
    "mydb",
    "show me all orders over $100",
    database="sales",
    collection="public",
)
```

**Vector sources** — no LLM needed; the query is embedded and run as KNN:

```python
results = registry.execute_query_nl(
    "docs",
    "documents about machine learning",
    collection="docs",
    optional_properties={"k": 10},
)
```

### Tool-based (`execute_query_nl_tools`)

Drives a multi-turn LLM tool loop where the model explores the source before writing a query. The LLM calls whichever tools it needs — it can inspect schema, sample rows, check column statistics, and (when called through the registry) fetch enriched metadata — then issues the final query.

Available tools in the loop:

| Tool | What it returns |
|---|---|
| `list_databases` | Database names |
| `list_collections` | Collection / schema names |
| `get_schema` | Entity and attribute list with types |
| `get_sample` | Sample rows + row count for a table |
| `get_column_stats` | Distinct count, min, max, null count, sample values |
| `get_relations` | Foreign key relationships |
| `execute_query` | Run a native query and return rows |
| `get_enriched_metadata` | Semantic types, descriptions, value semantics from the enrichment pipeline (registry path only) |

`get_enriched_metadata` is only available when calling through `DataRegistry.execute_query_nl_tools` — it reads from what the enrichment pipeline stored in the registry.

```python
# Source-level — no registry needed, no enriched metadata
rows = source.execute_query_nl_tools(
    query="which customers placed orders over $100?",
    database="sales",
    collection="public",
    llm_fn=llm_fn,   # (messages, tools, system=None) -> response dict
)

# Registry-level — includes get_enriched_metadata tool
rows = registry.execute_query_nl_tools(
    source="mydb",
    query="which customers placed orders over $100?",
    database="sales",
    collection="public",
)
```

`llm_fn` for the tool loop must accept `(messages, tools, system=None)` and return a response dict — the Anthropic tool-use API shape. The LLM used by the registry is pulled from the configured `metadata_enricher`.

See `examples/feature-demos/nl_tools_demo.py` for a full walkthrough.

---

## Data import and export

Move rows between registered sources, or export them directly to a file — no manual pandas or SQL boilerplate required.

### `import_data` — source to source

Copies rows from one registered DataSource into another. The transfer is **pull-based**: the target connects to the source and reads from it.

```python
registry.import_data(
    source="csv_store",    # registered name of the source to read from
    target="sqlite_store", # registered name of the target to write into
    database="shop",       # target database
    collection="orders",   # identifies the collection on the source side
    entity="orders",       # target table/entity name (required for SQL targets)
    mode="append",         # "append" (default) or "overwrite"
)
```

**`collection` vs `entity`**

These two parameters serve different sides of the transfer:

| Parameter | Side | Meaning |
|---|---|---|
| `collection` | Source | Which collection to read from (file stem for FileSource, table name for SQL sources) |
| `entity` | Target | Which table to write into on the SQL target |

They are separate because source and target may use different names for the same data. For `FileSource` targets, `entity` is not needed — the output filename is derived from `collection`.

**Source compatibility**

Any source that returns a flat list of rows from `execute_query(None, collection=...)` can be used as the source:

| Source type | Can be source | Can be target |
|---|---|---|
| `FileSource` | Yes | Yes |
| `SQLiteDBSource` | Yes | Yes |
| `PostgresDBSource` | Yes | Yes |
| `MySQLDBSource` | Yes | Yes |
| `GraphSource` | No — `execute_query` expects dict ops, not `None` | No |
| `VectorSource` | No | No |

**Modes**

- `"append"` — adds rows to existing data without touching what is already there.
- `"overwrite"` — clears the target table or file first, then writes the new rows.

**Examples**

File → SQL:
```python
registry.import_data(
    source="csv_store",
    target="sqlite_store",
    database="shop",
    collection="customers",  # reads customers.csv
    entity="customers",      # writes into the customers table
    mode="append",
)
```

SQL → SQL (same database name, different directories):
```python
registry.import_data(
    source="analytics_store",
    target="warehouse_store",
    database="shop",
    collection="top_customers",  # source table
    entity="top_customers",      # target table
    mode="append",
)
```

File → File (no `entity` needed):
```python
registry.import_data(
    source="csv_store",
    target="csv_backup",
    collection="orders",
    mode="append",
)
```

See `examples/feature-demos/import_data_demo.py` for a full walkthrough including overwrite mode and SQL → SQL transfer.

---

### `export_data` — source to file

Exports rows from a registered source directly to a file. Format is inferred from the file extension, or can be forced with `fmt`.

```python
registry.export_data(
    source="sqlite_store",          # registered source to read from
    path="/tmp/exports/orders.csv", # output file path
    database="shop",
    collection="orders",            # table or file to export
    query=None,                     # None = all rows; SQL string or dict = filter
    fmt=None,                       # inferred from extension: csv, json, jsonl, parquet
)
```

**Supported formats:** `csv`, `json`, `jsonl`, `parquet` — inferred from the file extension, or set explicitly with `fmt`.

**Filtering:** pass a query to export a subset of rows. For SQL sources this is a SQL string; for `FileSource` it is a `{column: value}` equality filter.

```python
# Export only paid orders to JSONL
registry.export_data(
    source="sqlite_store",
    path="/tmp/exports/paid_orders.jsonl",
    database="shop",
    collection="orders",
    query="SELECT * FROM orders WHERE status = 'paid'",
)
```

`export_data` is a registry-level convenience — there is no `DataSource.export_data` method. It always reads via `execute_query` and writes using pandas.

See `examples/feature-demos/export_data_demo.py` for a full walkthrough including CSV, JSON, and filtered JSONL exports.

---

## MCP server

Exposes registry operations as tools for Claude and other MCP clients, enabling AI agents to explore and query your data autonomously.

```bash
# Start the MCP server (stdio transport)
blue-data-registry-mcp

# With a pre-loaded source config
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp
```

**Claude Desktop config:**

```json
{
  "mcpServers": {
    "blue-data-registry": {
      "command": "blue-data-registry-mcp",
      "env": {
        "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json"
      }
    }
  }
}
```

See [`docs/registry-mcp.md`](registry-mcp.md) for the full tool reference.

---

## REST API and CLI

Full platform layer for production deployments and scripting.

**REST API:**

```bash
blue-data-api  # starts on http://localhost:8000
# interactive docs at http://localhost:8000/docs
```

**CLI:**

```bash
blue-registry source add shop --type sqlite --database-dir /data/shop
blue-registry source sync shop
blue-registry source stats shop
blue-registry source enrich shop
blue-registry search "revenue"
blue-registry source inspect shop mydb public orders
```

See [`docs/api.md`](api.md) and [`docs/cli.md`](cli.md) for full references.

---

## Why blue-data

LLMs querying enterprise data fail in predictable, silent ways. blue-data fixes the root cause — not the prompt.

**Coded value disambiguation**

A Czech banking database stores transaction types as `PRIJEM`, `VYDAJ`, `UVER`. Ask an LLM *"how many credit transactions in 1997?"* and it writes `WHERE type = 'credit'` — returning 0 rows with no error. blue-data Layer 1 auto-detects these ENUM columns and captures the actual coded values from data. The LLM now writes `WHERE type = 'PRIJEM'` and gets the right answer. No annotation, no LLM cost, no schema changes.

**Semantic data discovery**

A column named `freight` doesn't match a search for *"shipping cost"*. A column named `units_in_stock` doesn't match *"current inventory"*. Agents and analysts searching by meaning find nothing. blue-data Layer 2 generates natural-language descriptions for every column — once, cheaply — and stores them in the registry. After enrichment, *"shipping cost"* finds `orders.freight`. *"No longer sold"* finds `products.discontinued`. Zero API calls at search time.

**Data quality before querying**

A query that looks syntactically correct returns an average salary of $2 million. The cause: one test record with value `9999999`, country stored inconsistently as both `"US"` and `"United States"`, and sentinels like `"N/A"` masquerading as data in the email field. An LLM cannot detect any of this without inspecting the data, and it has no way to know the query result is wrong. blue-data DQ profiling surfaces every issue before a query runs — outlier rate, representation fragmentation, disguised missing values, suspected typos — stored as registry properties that agents can read and act on. The corrected query returns the right answer.

**Process and temporal reasoning**

Event-log tables get treated as static snapshots. *"What is the current account balance?"* produces `AVG(balance)` — averaging all historical records instead of reading the most recent one. *"Monthly trend"* produces a flat `COUNT(*)` with no time grouping. blue-data Layer 1 detects EVENT tables, identifies the event-time column, classifies state variables, and injects process operators into the schema context. The LLM now writes temporally correct queries — with `ORDER BY date`, `GROUP BY month`, and proper window logic. No LLM cost.
