# registry-mcp

MCP server that exposes `DataRegistry` operations as tools for LLM clients
(Claude Desktop, Claude Code, and any MCP-compatible host).

---

## Installation

```bash
cd platform/registry-mcp

# Install the core library first
pip install -e ../../lib

# Install the MCP server
pip install -e .

# Optional: Redis backend
pip install -e ".[redis]"

# Optional: LLM-augmented enrichment
pip install -e ".[llm]"
```

---

## Running

```bash
# Default: in-memory registry, no pre-loaded sources
blue-data-registry-mcp

# Pre-load sources from a JSON config file
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp

# Persistent registry backed by Redis
BLUE_DATA_REGISTRY_STORE=redis \
BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \
    blue-data-registry-mcp

# LLM-augmented enrichment (Anthropic)
BLUE_DATA_LLM_PROVIDER=anthropic \
ANTHROPIC_API_KEY=sk-ant-... \
    blue-data-registry-mcp
```

---

## Claude Desktop integration

Add to `~/.config/claude-desktop/claude_desktop_config.json`:

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

If `blue-data-registry-mcp` is not on the system PATH, use the full path:

```json
{
  "mcpServers": {
    "blue-data-registry": {
      "command": "/path/to/venv/bin/blue-data-registry-mcp",
      "env": {
        "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json"
      }
    }
  }
}
```

---

## Configuration reference

All configuration is via environment variables.

### Storage backend

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_STORE` | `memory` | `memory` — ephemeral in-process registry. `file` — JSON file on disk. `redis` — persistent Redis-backed registry (requires Redis Stack). |
| `BLUE_DATA_REGISTRY_FILE` | `blue_data_store.json` | Path to the registry JSON file. Used when `BLUE_DATA_REGISTRY_STORE=file`. |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Used when `BLUE_DATA_REGISTRY_STORE=redis`. Supports `user:password@` auth and the `rediss://` TLS scheme. |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key prefix used to isolate registry records in Redis. |

### LLM enrichment

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_LLM_PROVIDER` | _(none)_ | Set to `anthropic` or `openai` to enable LLM-augmented enrichment. Blank = deterministic-only. |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when `BLUE_DATA_LLM_PROVIDER=anthropic`. |
| `OPENAI_API_KEY` | _(none)_ | Required when `BLUE_DATA_LLM_PROVIDER=openai`. |
| `BLUE_DATA_LLM_MODEL` | _(none)_ | Model for LLM enrichment; blank resolves per provider (`claude-opus-4-8` / `gpt-4o`). |

### Source pre-loading

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_SOURCES_CONFIG` | _(none)_ | Path to a JSON file defining data sources to register on startup. |

**Config file format:**

```json
{
  "sources": [
    {
      "type": "sqlite",
      "name": "sales",
      "properties": {
        "connection": { "database_directory": "/data/sqlite-dbs" }
      }
    },
    {
      "type": "postgres",
      "name": "warehouse",
      "properties": {
        "connection": {
          "host": "localhost",
          "port": 5432,
          "user": "blue_data_ro",
          "password": "<password>",
          "database": "warehouse"
        }
      }
    }
  ]
}
```

Supported source types: `sqlite`, `postgres`.

> **Use a least-privilege database role.** `query` runs read-only (writes need
> `commit=true`, honored only when the API enables it), and non-read statements are
> refused before they run. But a privileged `SELECT` — e.g. `pg_read_file()` — still
> executes with the connection's rights, so connect as a dedicated read-only role,
> **not** `postgres`/`root`. See blue-data `docs/configuration.md` for the grants.

---

## Tool reference

### Explore tools

#### `search_records`

Search registry records by keyword or semantic similarity.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Natural-language search query |
| `record_type` | `str \| None` | `None` | Filter to one type: `source`, `database`, `collection`, `entity`, `attribute`, `relation` |
| `scope` | `str \| None` | `None` | Restrict to a registry path subtree, e.g. `/source/sales/database/prod` |
| `limit` | `int` | `10` | Maximum results to return |

Returns a ranked list of records, each with `name`, `type`, `scope`, `description`, and `_score`.

---

#### `list_sources`

List the names of all registered data sources.

Returns `["sales", "warehouse", ...]`.

---

#### `list_source_databases`

List all databases registered under a source.

| Parameter | Type | Description |
|---|---|---|
| `source` | `str` | Source name |

---

#### `list_database_collections`

List all collections (schemas) within a database.

| Parameter | Type | Description |
|---|---|---|
| `source` | `str` | Source name |
| `database` | `str` | Database name |

---

#### `list_collection_entities`

List all entities (tables) within a collection.

| Parameter | Type | Description |
|---|---|---|
| `source` | `str` | Source name |
| `database` | `str` | Database name |
| `collection` | `str` | Collection name (typically `public` for SQL sources) |

---

### Inspect tools

#### `get_entity`

Get full details for an entity — description, stats, enrichment properties, and all
attributes with their `value_semantics`, `semantic_role`, `quantitative_vst`,
`process_vst_role`, and `semantic_discovery` inline.

| Parameter | Type | Description |
|---|---|---|
| `source` | `str` | Source name |
| `database` | `str` | Database name |
| `collection` | `str` | Collection name |
| `entity` | `str` | Entity name |

Returns a single record object with an `attributes` array.

---

#### `get_record`

Get a specific registry record by its `(name, type, scope)` identity.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Record name |
| `record_type` | `str` | `source`, `database`, `collection`, `entity`, `attribute`, or `relation` |
| `scope` | `str` | Full parent path, e.g. `/source/sales/database/prod/collection/public` |

---

### Manage tools

These tools require the source to be registered and connected. The typical
workflow is: `sync_source` → `collect_source_stats` → `enrich_source_metadata`.

#### `sync_source`

Sync registry records from a live data source. Idempotent — safe to call
repeatedly.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | required | Source name |
| `recursive` | `bool` | `True` | Descend through all levels |

---

#### `collect_source_stats`

Collect statistics (row counts, sample values, min/max, distinct counts) from a
live source and store them in registry records. Required before enrichment.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | required | Source name |
| `recursive` | `bool` | `True` | Collect at all levels |

---

#### `enrich_source`

Run deterministic semantic type inference on all attributes. Detects `INTEGER`,
`FLOAT`, `DATE`, `EMAIL`, `ENUM_CATEGORY`, `FREE_TEXT`, `UUID`, and more.
Requires stats to have been collected first.

| Parameter | Type | Description |
|---|---|---|
| `source` | `str` | Source name |

---

#### `enrich_source_metadata`

Run the full `MetaData` enrichment pipeline. Adds semantic roles, quantitative
VST classifications, process semantics, and statistical relationship signals
between attributes. With `BLUE_DATA_LLM_PROVIDER` set, also runs LLM-augmented
enrichments (value semantics inference, semantic discovery, entity descriptions).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | required | Source name |
| `recursive` | `bool` | `True` | Enrich all levels |
| `rebuild` | `bool` | `False` | `False` = skip already-enriched properties (idempotent). `True` = overwrite everything. |

### Query tools

#### `execute_query`

Execute a native query against a registered data source and return rows.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | required | Source name |
| `query` | `str` | required | Native query string (e.g. a SQL SELECT statement) |
| `database` | `str \| None` | `None` | Database name (required for SQL sources) |
| `collection` | `str \| None` | `None` | Collection / schema name (optional) |

Returns a JSON array of row objects.

---

#### `import_data`

Import rows from one registered data source into another.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | required | Source data source (origin) |
| `target` | `str` | required | Target data source (destination) |
| `collection` | `str` | `"default"` | Collection / table / file name to read from the source |
| `database` | `str` | `"default"` | Database name on the target |
| `entity` | `str \| None` | `None` | Destination table name on the target (required for SQL targets) |
| `mode` | `str` | `"append"` | `append` adds rows; `overwrite` clears the target first |

---

## Typical session

```
# 1. Find what sources are registered
list_sources()

# 2. Explore the hierarchy
list_source_databases("sales")
list_database_collections("sales", "prod")
list_collection_entities("sales", "prod", "public")

# 3. Inspect an entity in detail
get_entity("sales", "prod", "public", "orders")

# 4. Search across the registry
search_records("customer revenue monthly")
search_records("date columns", record_type="attribute")

# 5. Refresh and enrich (if the source is connected)
sync_source("sales")
collect_source_stats("sales")
enrich_source_metadata("sales")

# 6. Re-inspect after enrichment
get_entity("sales", "prod", "public", "orders")
```

---

## Architecture

```
Claude / MCP client
        │  MCP (stdio transport)
        ▼
registry_mcp.server   ← FastMCP app, 13 tool handlers
        │
registry_mcp.config   ← singleton DataRegistry factory
        │
        ▼
   DataRegistry        ← lib/src/blue-data/registry/
   ├── JSONSource       ← MemoryJSONSource | RedisJSONSource
   ├── VectorSource     ← (optional — not wired by default)
   └── MetaData         ← deterministic | LLM-augmented
```

The server holds a single `DataRegistry` instance per process. All tool calls
share that instance, so state (registered sources, synced records, enrichment)
persists for the lifetime of the server process.

With `BLUE_DATA_REGISTRY_STORE=redis`, the registry state persists across server restarts.
With `BLUE_DATA_REGISTRY_STORE=memory` (default), it is ephemeral.

---

## Running tests

```bash
cd platform/registry-mcp
python3 -m pytest tests/ -v
```

Tests inject an in-memory registry directly — no Redis, no API keys, no network
required.
