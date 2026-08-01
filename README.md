# blue-data

blue-data is a data intelligence layer for AI applications. It provides a unified interface to register, introspect, and query heterogeneous data sources such as SQL databases, document stores, and graph databases — and enriches them with semantic metadata that makes data understandable to AI agents and language models. It sits between raw data and the AI layer, answering questions like: what data exists, what it means, how it relates, and how it can safely be queried.

Its core capabilities include:

- **Unified access** across heterogeneous enterprise data sources
- **Deep data discoverability** to identify the most relevant data for a given task
- **Fine-grained semantic understanding** of schemas, tables, columns, relationships, business semantics, and values
- **Task-aware intelligence** to determine whether available data is sufficient and appropriate to accomplish a specific task
- **Cross-source intelligence** that understands relationships and semantics across multiple enterprise systems
- **AI-ready semantic metadata** that enables more accurate reasoning, planning, and decision-making over enterprise data

→ **[Full feature list](docs/features.md)** · **[Installation](docs/installation.md)**

## Installation

```bash
cd lib && ./scripts/install.sh
```

Install `lib` first — all platform components depend on it. For full setup instructions (all components, optional extras, Redis Stack requirement, build/publish scripts) see **[docs/installation.md](docs/installation.md)**.

## Concepts

**DataSource** — an adapter for an external data store (SQLite, Postgres, Redis, etc.). Each source exposes a consistent interface for listing databases, collections, entities, relations, and executing queries.

**DataRegistry** — a catalog that tracks registered sources and mirrors their structure (databases → collections → entities → attributes) as addressable records. Records carry metadata, descriptions, properties, statistics, and are searchable.

**JSONSource** — the storage backend for the registry itself. Defaults to in-memory (`MemoryJSONSource`) for development; `RedisJSONSource` is the production backend.

**VectorSource** — pluggable vector index used by the search engine. `MemoryVectorSource` for dev/test; `RedisVectorSource` for production (requires Redis Stack).

**Plan** — a DAG of `PlanNode` objects (`INPUT`, `OUTPUT`, `OPERATOR`) used to represent and execute data transformation pipelines.

## Quick start

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

# Sync source structure into the registry
registry.sync_source("sqlite", recursive=True)

# List what was discovered
print(registry.list_source_databases("sqlite"))
print(registry.list_database_collections("sqlite", "mydb"))
print(registry.list_collection_entities("sqlite", "mydb", "public"))
```

## Search

`DataRegistry` supports hybrid search (BM25 keyword + vector similarity) over all registry records. Pass a `VectorSource` and an embedding function to enable vector search; omit them to fall back to keyword-only.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

# In-memory search — no Redis required
registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=my_embedding_fn,   # callable: str → list[float]
    vector_dim=1536,
    rebuild=True,
)

registry.register_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Stores user accounts and profile data",
)

results = registry.search_records("user accounts")
for r in results:
    print(r["name"], r.get("_score"))
```

## Syncing and stats

```python
# Sync a specific collection
registry.sync_source_database_collection("sqlite", "mydb", "public")

# Collect stats at various levels
registry.collect_source_database_stats("sqlite", "mydb")
registry.collect_source_database_collection_stats("sqlite", "mydb", "public")
registry.collect_source_database_collection_entity_stats("sqlite", "mydb", "public", "users")
registry.collect_source_database_collection_entity_attribute_stats(
    "sqlite", "mydb", "public", "users", "name"
)
```

## Enrichment

`blue-data` enriches registry records with two layers of intelligence.

**Layer 1 — Deterministic** (`enrich_source`): runs `SemanticTypeInferencer` on every attribute's sample values and writes the detected semantic type to `attribute.properties["value_semantics"]`. No API key or LLM required.

**Layer 2 — MetaData pipeline** (`enrich_source_metadata`): builds on Layer 1 and adds process semantics, semantic roles, value-axis detection, statistical relationship signals, and — when an `llm_fn` is provided — LLM-augmented enrichments (VSI, SDI, domain concept, entity descriptions).

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

# Deterministic-only (no API key needed)
enricher = MetaData(llm_fn=None)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)

# Prerequisite order must be followed:
registry.sync_all(recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
```

To enable LLM-augmented enrichment, install `anthropic` (`pip install "blue-data[llm]"`) and pass an `llm_fn`:

```python
import anthropic

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

`llm_fn` is provider-agnostic — any callable `(str) -> str` works (OpenAI, local models, test stubs).

`rebuild=False` is idempotent: existing enrichment properties are not overwritten on subsequent calls. Use `rebuild=True` to force re-enrichment.

## Natural language queries

`DataRegistry.execute_query_nl` lets you query a registered source in plain English. The translation strategy depends on the source type.

### SQL / graph sources — LLM pipeline

For SQL (SQLite, Postgres, MySQL) and graph (Neo4j) sources the pipeline is:

```
NL query
  → _format_schema_for_nl()    # renders entity/attribute list as text
  → _build_nl_prompt()         # adds dialect-specific instructions ("write a SQL SELECT…")
  → llm_fn(prompt)             # LLM produces the native query
  → _extract_native_query()    # strips markdown fences, cleans output
  → execute_query()            # runs the native query and returns rows
```

The `llm_fn` comes from the `metadata_enricher` configured on the registry. Schema context is pulled from the registry records (entities and attributes) to ground the LLM prompt.

```python
import anthropic
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

client = anthropic.Anthropic()

def llm_fn(prompt: str) -> str:
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

registry = DataRegistry(
    store=MemoryJSONSource(),
    metadata_enricher=MetaData(llm_fn=llm_fn),
)
registry.sync_all(recursive=True)
registry.collect_source_stats("mydb", recursive=True)

rows = registry.execute_query_nl(
    "mydb",
    "show me all orders over $100",
    database="sales",
    collection="public",
)
```

Returns `[]` when no `llm_fn` is configured.

### Vector sources — embedding pipeline

For `VectorSource` backends (MemoryVectorSource, ChromaDBVectorSource, RedisVectorSource, FileVectorSource) **no LLM is needed**. The NL query is embedded into a vector and run as a KNN search:

```
NL query
  → embedding_fn(query)   # registry's embedding function produces a query vector
  → knn(index, vector)    # nearest neighbours by cosine similarity
  → rows
```

The registry automatically injects its `embedding_fn` when the target source is a VectorSource.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

def embed(text: str) -> list[float]:
    ...  # your embedding function

vec_src = MemoryVectorSource("docs")
# ... create index and upsert docs with embeddings ...

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),   # registry search index
    embedding_fn=embed,
    vector_dim=1536,
)
registry.register_source(vec_src)

results = registry.execute_query_nl(
    "docs",
    "documents about machine learning",
    collection="docs",              # index name to search
    optional_properties={"k": 10}, # number of nearest neighbours
)
```

Returns `[]` when no embedding function is configured on the registry.

### Extending NL translation

To add custom (rule-based or DSL) translation to a new source, override `translate_nl_to_native_query` — the single hook point for translation strategy:

```python
class MySource(DataSource):
    def translate_nl_to_native_query(self, query, schema, llm_fn):
        # llm_fn is available but can be ignored for rule-based translation
        return my_dsl_parser(query)
```

Override `execute_query_nl` instead only when the *execution shape* differs from a plain `execute_query` call (e.g. MongoDB wraps the filter in a `FIND` op dict).

## Implementing a new DataSource

Subclass `DataSource` and override the methods your backend supports:

```python
from blue_data.source.source import DataSource

class MySource(DataSource):
    def fetch_databases(self) -> list[str]: ...
    def fetch_database_collections(self, database: str) -> list[str]: ...
    def fetch_database_collection_entities(self, database: str, collection: str) -> dict: ...
    def execute_query(self, query, database=None, collection=None, optional_properties=None): ...
```

`fetch_database_collection_entities` should return a dict keyed by entity name. Each value follows the `DataSchema` entity format:

```python
{
  "users": {
    "name": "users",
    "properties": {},
    "contents": {
      "attributes": {
        "id":   {"name": "id",   "info": {"type": "INTEGER"}, "description": None},
        "name": {"name": "name", "info": {"type": "TEXT"},    "description": None},
      }
    }
  }
}
```

## Examples

After installing with `pip install -e .`:

**Backends**

| File | Description |
|---|---|
| `examples/backends/registry_memory_example.py` | Pure in-memory `Registry` and `DataRegistry` — CRUD, filter, search, dumps/loads. No external dependencies. |
| `examples/backends/sqlite_data_registry_demo.py` | Full pipeline with SQLite — sync, stats, enrich, relations, connect_source, search, MetaData enrichment. No external dependencies. |
| `examples/backends/redis_demo.py` | Redis Stack + PostgreSQL (falls back to SQLite) — Redis-backed registry and search index, namespace isolation, full hierarchy walk. Requires Redis Stack. |

**Feature demos**

| File | Description |
|---|---|
| `examples/feature-demos/enrichment_demo.py` | Enrichment deep-dive — `SemanticTypeInferencer` standalone, Mode A (deterministic), Mode B (LLM-augmented with Anthropic SDK), idempotency and rebuild. |

**Pipeline demos**

| File | Description |
|---|---|
| `examples/pipeline-demos/sql_semantic_enrichment_demo.py` | Full pipeline against the Northwind multi-table schema — register, sync, enrich, search the registry, execute SQL. No external dependencies for enrichment. |

**Scenario demos**

| File | Description |
|---|---|
| `examples/scenario-demos/coded_value_demo.py` | Coded value disambiguation — auto-detects ENUM columns and captures actual coded values so NL queries find the right rows. |
| `examples/scenario-demos/description_search_demo.py` | Description-enriched discovery — Layer 2 generates attribute descriptions; registry search finds columns by semantic meaning. |
| `examples/scenario-demos/process_reasoning_demo.py` | Process reasoning — Layer 1 detects EVENT tables and process operators, grounding SQL generation in temporal semantics. |

**Integration demos**

| File | Description |
|---|---|
| `examples/integration-demos/langgraph_direct_demo.py` | LangGraph 3-node pipeline (discover → translate → execute) calling blue-data Python API directly. Requires `langgraph`, `langchain-openai`, and `OPENAI_API_KEY`. |
| `examples/integration-demos/langgraph_mcp_demo.py` | LangGraph ReAct agent using blue-data's `registry-mcp` server as tools via `langchain-mcp-adapters`. No blue-data imports on the agent side. Requires `registry-mcp` running and `OPENAI_API_KEY`. |

```bash
# In-memory demo (no deps)
python3 examples/backends/registry_memory_example.py

# SQLite demo (no deps)
python3 examples/backends/sqlite_data_registry_demo.py

# Enrichment demo: Mode A runs without deps; Mode B requires ANTHROPIC_API_KEY
python3 examples/feature-demos/enrichment_demo.py

# Redis + Postgres demo (requires Redis Stack; falls back to SQLite)
python3 examples/backends/redis_demo.py

# LangGraph direct API demo (requires langgraph, langchain-openai, OPENAI_API_KEY)
pip install langgraph langchain-core langchain-openai
python3 examples/integration-demos/langgraph_direct_demo.py

# LangGraph MCP demo (requires langchain-mcp-adapters, registry-mcp running, OPENAI_API_KEY)
pip install langgraph langchain-mcp-adapters
blue-data-registry-mcp  # start in a separate terminal
python3 examples/integration-demos/langgraph_mcp_demo.py
```

## Demo databases

The `data/` directory contains the **Northwind** sales schema — a 7-table dataset (categories, customers, employees, orders, order\_details, products, suppliers) with FK relations and sample data.

| File | Use |
|---|---|
| `data/northwind_sqlite.sql` | Load into SQLite: `sqlite3 northwind.db < data/northwind_sqlite.sql` |
| `data/northwind_postgres.sql` | Load into Postgres: `psql -U postgres -d northwind -f data/northwind_postgres.sql` |

## Configuration

All platform components (API, CLI, MCP servers) are configured via environment variables. Copy `example.envrc` to `.envrc` and fill in your values — `.envrc` is gitignored and never committed.

```bash
cp example.envrc .envrc
source .envrc
```

Variables can also be set inline or exported in your shell. The sections below document every supported variable, its default, and when it is required.

---

### Store

Controls where the registry state is persisted.

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_STORE` | `memory` | Persistence backend: `memory`, `redis`, or `file` (json-mcp only) |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Required when `BLUE_DATA_REGISTRY_STORE=redis` |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key namespace prefix in Redis. Isolates multiple registry instances on the same server |
| `BLUE_DATA_REGISTRY_FILE` | `blue_data_store.json` | Path to JSON file. Required when `BLUE_DATA_REGISTRY_STORE=file` (json-mcp only) |

> **Redis Stack required**: `BLUE_DATA_REGISTRY_STORE=redis` uses `JSON.SET` and `FT.CREATE` commands only available in Redis Stack (`redis-stack-server`), not plain Redis.

---

### LLM

Enables AI-augmented metadata enrichment. Leave `BLUE_DATA_LLM_PROVIDER` blank to run in deterministic-only mode (no API key needed).

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_LLM_PROVIDER` | _(empty)_ | LLM provider: `anthropic` or `openai`. Leave blank to disable LLM enrichment |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` (anthropic) / `gpt-4o` (openai) | Model name passed to the provider API |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required when `BLUE_DATA_LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | _(empty)_ | Required when `BLUE_DATA_LLM_PROVIDER=openai` |

---

### Search tuning

Controls the hybrid search engine inside `DataRegistry`. Defaults are tuned for general use — adjust if your registry has specific recall/precision requirements.

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_VECTOR_DIM` | `1536` | Embedding vector dimension. Must match your embedding model's output size |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT` | `0.3` | Weight of BM25 keyword score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT` | `0.7` | Weight of vector similarity score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT` | `0.15` | Weight of value-relevance score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD` | `0.0` | Minimum BM25 score for a record to be considered |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD` | `0.5` | Minimum vector similarity score for a record to be considered |
| `BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD` | `0.36` | Minimum combined score for a record to appear in results |
| `BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL` | `true` | Enable hierarchical search — propagates child scores to parent records when searching by `database` or `collection` type |

Search weights do not need to sum to 1 — they are normalized automatically.

---

### Sources

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_SOURCES_CONFIG` | _(empty)_ | Path to a JSON file that pre-loads data sources into the registry at startup |

Source config file format:

```json
{
  "sources": [
    {
      "type": "sqlite",
      "name": "mydb",
      "properties": { "connection": { "database_directory": "/data/dbs" } }
    },
    {
      "type": "postgres",
      "name": "prod",
      "properties": { "connection": { "host": "localhost", "port": 5432, "database": "myapp", "user": "postgres", "password": "" } }
    }
  ]
}
```

Supported source types: `sqlite`, `postgres`, `mysql`, `mongodb`.

---

## Platform

The `platform/` directory contains deployable components built on top of `lib/`.

| Component | Description | Status |
|---|---|---|
| `platform/registry-mcp` | MCP server — exposes registry ops as tools for Claude and MCP clients | ✅ Done |
| `platform/api` | REST API | ✅ Done |
| `platform/cli` | Command-line interface | ✅ Done |
| `platform/json-mcp` | MCP server for raw JSONSource operations (memory + file) | ✅ Done |

### registry-mcp quick start

```bash
# Install
cd platform/registry-mcp
pip install -e ../../lib
pip install -e .

# Run (stdio transport — for Claude Desktop / Claude Code)
blue-data-registry-mcp

# Pre-load sources from a config file
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp

# Persistent registry backed by Redis
BLUE_DATA_REGISTRY_STORE=redis BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \
    blue-data-registry-mcp

# LLM-augmented enrichment tools
BLUE_DATA_LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... \
    blue-data-registry-mcp
```

**Claude Desktop config** (`~/.config/claude-desktop/claude_desktop_config.json`):

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

Source config file format (`sources.json`):

```json
{
  "sources": [
    {
      "type": "sqlite",
      "name": "mydb",
      "properties": { "connection": { "database_directory": "/data/dbs" } }
    }
  ]
}
```

See [`docs/registry-mcp.md`](docs/registry-mcp.md) for the full tool reference and all configuration options.

### api quick start

```bash
cd platform/api
pip install -e ../../lib
pip install -e .

# dev server (auto-reload)
uvicorn registry_api.main:app --reload --port 8000

# or via the installed script
blue-data-api
```

Interactive docs at `http://localhost:8000/docs`.  
Pre-load sources with `BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json` (same format as registry-mcp).  
See [`docs/api.md`](docs/api.md) for the full endpoint reference.

### cli quick start

```bash
cd platform/cli
pip install -e ../../lib
pip install -e .

# Register a source and run the full pipeline
blue-data sources add shop --type sqlite --database-dir /data/shop
blue-data sync shop
blue-data stats shop
blue-data enrich shop
blue-data metadata shop          # add BLUE_DATA_LLM_PROVIDER=anthropic for LLM enrichment

# Search and inspect
blue-data search "revenue"
blue-data inspect entity shop prod public orders

# Use --json for scripting
blue-data --json search "orders" | jq '.[].name'
```

Pre-load sources with `BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json` (same format as other platforms).  
See [`docs/cli.md`](docs/cli.md) for the full command reference.

---

## Running tests

See **[docs/installation.md](docs/installation.md)** for the full test setup.
