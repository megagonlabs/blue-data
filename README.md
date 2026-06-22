# blue-data

Blue Data Intelligence Layer — a Python library for registering, introspecting, and querying heterogeneous data sources through a unified interface.

## Installation

**Configure** — copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```
`.env` is gitignored. See `.env.example` for the full list of supported variables (store, LLM provider, search weights, sources config path).

**Install everything** (lib + all platform components, editable with dev extras):
```bash
make install
```

**Install individual components:**
```bash
make install-lib           # core lib only
make install-api           # REST API
make install-cli           # CLI
make install-json-mcp      # JSON MCP server
make install-registry-mcp  # registry MCP server
```

Each platform component automatically installs the core lib as a dependency.

**Build distributable packages** (wheel + sdist into each component's `dist/`):
```bash
make build                 # all components
make build-lib             # core lib only
make build-api             # REST API
make build-cli             # CLI
make build-json-mcp        # JSON MCP server
make build-registry-mcp    # registry MCP server
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
BLUE_DATA_CONFIG=/path/to/sources.json blue-data-registry-mcp

# Persistent registry backed by Redis
BLUE_DATA_STORE=redis BLUE_DATA_REDIS_URL=redis://localhost:6379/0 \
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
        "BLUE_DATA_CONFIG": "/path/to/sources.json"
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
Pre-load sources with `BLUE_DATA_CONFIG=/path/to/sources.json` (same format as registry-mcp).  
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

Pre-load sources with `BLUE_DATA_CONFIG=/path/to/sources.json` (same format as other platforms).  
See [`docs/cli.md`](docs/cli.md) for the full command reference.

---

## Running tests

From the repo root:

```bash
make test                  # all unit tests (lib + all platform components)
make test-lib              # lib unit tests only
make test-platform         # all platform component tests
make test-api              # REST API tests
make test-cli              # CLI tests
make test-json-mcp         # JSON MCP tests
make test-registry-mcp     # registry MCP tests
make test-lib-integration  # lib integration tests (requires Redis, Postgres, MySQL, Neo4j)
```

Run `make help` to see all available targets.

If packages are not yet installed, run `make install` first:

```bash
make install   # installs all packages with dev extras
make test
```

Redis integration tests auto-skip when Redis Stack is not running. To run them:

```bash
redis-stack-server --port 6379 --daemonize yes
make test-lib-integration
```
