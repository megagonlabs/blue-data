# blue-data

Blue Data Intelligence Layer — a Python library for registering, introspecting, and querying heterogeneous data sources through a unified interface.

## Installation

Each component has a `scripts/` directory. Run scripts from the component's root directory.

| Script | Components | Purpose |
|---|---|---|
| `build.sh` | all | Build wheel + sdist into `dist/` |
| `install.sh` | all | Editable install (`python3 -m pip install -e .`) |
| `publish.sh` | lib only | Publish to package registry via twine |

**Install a component (editable):**
```bash
cd lib && ./scripts/install.sh
cd platform/api && ./scripts/install.sh
cd platform/cli && ./scripts/install.sh
cd platform/json-mcp && ./scripts/install.sh
cd platform/registry-mcp && ./scripts/install.sh
```

Install `lib` first — all platform components depend on it.

**Build distributable packages:**
```bash
cd lib && ./scripts/build.sh
cd platform/api && ./scripts/build.sh
cd platform/cli && ./scripts/build.sh
cd platform/json-mcp && ./scripts/build.sh
cd platform/registry-mcp && ./scripts/build.sh
```

Requires the `build` package (`pip install build`).

## Runtime dependencies

- `pandas`, `numpy` — always required

Optional extras (install with `pip install -e ".[redis]"` etc.):

| Extra | Packages | Required for |
|---|---|---|
| `redis` | `redis` | `RedisJSONSource`, `RedisVectorSource`, `RedisStreamSource` |
| `postgres` | `psycopg2-binary` | `PostgresDBSource` |
| `mysql` | `mysql-connector-python` | `MySQLDBSource` |
| `mongodb` | `pymongo` | `MongoDBJSONSource` |
| `neo4j` | `neo4j` | `Neo4jGraphSource` |
| `llm` | `anthropic` | LLM-augmented enrichment via `MetaData(llm_fn=...)` |

> **Redis Stack required:** `RedisJSONSource` and `RedisVectorSource` use `JSON.SET` and `FT.CREATE` commands that are not available in standard Redis. You need **Redis Stack** (`redis-stack-server`), not plain `redis`.

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

| File | Description |
|---|---|
| `examples/registry_memory_example.py` | Pure in-memory `Registry` and `DataRegistry` — CRUD, filter, search, dumps/loads. No external dependencies. |
| `examples/sqlite_data_registry_demo.py` | Full pipeline with SQLite — sync, stats, enrich, relations, connect_source, search, MetaData enrichment. No external dependencies. |
| `examples/enrichment_demo.py` | Enrichment deep-dive — `SemanticTypeInferencer` standalone, Mode A (deterministic), Mode B (LLM-augmented with Anthropic SDK), idempotency and rebuild. |
| `examples/redis_demo.py` | Redis Stack + PostgreSQL (falls back to SQLite) — Redis-backed registry and search index, namespace isolation, full hierarchy walk. Requires Redis Stack. |

```bash
# In-memory demo (no deps)
python3 examples/registry_memory_example.py

# SQLite demo (no deps)
python3 examples/sqlite_data_registry_demo.py

# Enrichment demo: Mode A runs without deps; Mode B requires ANTHROPIC_API_KEY
python3 examples/enrichment_demo.py

# Redis + Postgres demo (requires Redis Stack; falls back to SQLite)
python3 examples/redis_demo.py
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

Run from each component's root directory:

```bash
cd lib && pytest tests/unit -v           # lib unit tests
cd platform/api && pytest -v             # REST API tests
cd platform/cli && pytest -v             # CLI tests
cd platform/json-mcp && pytest -v        # JSON MCP tests
cd platform/registry-mcp && pytest -v   # registry MCP tests
```

Install packages with dev extras before running tests:

```bash
cd lib && ./scripts/install.sh
```

Redis integration tests auto-skip when Redis Stack is not running. To run them:

```bash
redis-stack-server --port 6379 --daemonize yes
cd lib && pytest tests/integration -v
```
