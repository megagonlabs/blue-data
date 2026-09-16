# blue-data CLI

`platform/cli` is a command-line interface for blue-data DataRegistry operations.

## Installation

```bash
cd platform/cli
pip install -e ../../lib
pip install -e .
```

## Usage

```
blue-data [--json] [--store memory|redis] [--config PATH] COMMAND
```

`--json` switches all output to raw JSON. `--store` and `--config` override the
`BLUE_DATA_REGISTRY_STORE` and `BLUE_DATA_SOURCES_CONFIG` environment variables respectively.

## Environment variables

Same set as `registry-mcp` and `api`:

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_STORE` | `memory` | `memory` or `redis` |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis URL (when store=redis) |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key prefix for Redis |
| `BLUE_DATA_LLM_PROVIDER` | _(none)_ | `anthropic` to enable LLM enrichment |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when LLM provider is anthropic |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` | Model ID for LLM enrichment |
| `BLUE_DATA_SOURCES_CONFIG` | _(none)_ | Path to JSON source config file |

## Source config file

Pre-load sources at startup:

```json
{
  "sources": [
    {
      "type": "sqlite",
      "name": "mydb",
      "properties": {
        "connection": { "database_directory": "/data/sqlite" }
      }
    }
  ]
}
```

---

## Commands

### `source`

All source operations are grouped under `source`.

#### `source list`

```bash
blue-data source list
```

#### `source add`

```bash
blue-data source add NAME --type sqlite --database-dir /path/to/dbs
blue-data source add NAME --type postgres --host localhost --dbname mydb \
    --user app --password <password>
```

#### `source remove`

```bash
blue-data source remove NAME
```

#### `source sync`

Walk the live source and register all databases, collections, entities, and attributes.

```bash
blue-data source sync mydb                    # recursive by default
blue-data source sync mydb --no-recursive     # top-level only
```

#### `source stats`

Collect row counts, null rates, and value statistics from the live source.

```bash
blue-data source stats mydb
blue-data source stats mydb --no-recursive
```

#### `source enrich`

Run deterministic semantic type inference (BOOLEAN, INTEGER, EMAIL, UUID, etc.) on all attributes.

```bash
blue-data source enrich mydb
```

#### `source metadata`

Run the full MetaData enrichment pipeline (semantic roles, VST, process semantics, semantic links,
and — when `BLUE_DATA_LLM_PROVIDER=anthropic` — LLM-augmented enrichment).

```bash
blue-data source metadata mydb
blue-data source metadata mydb --rebuild      # overwrite existing enrichment
```

#### `source query`

Execute raw SQL against a live source:

```bash
blue-data source query mydb "SELECT * FROM orders LIMIT 5" --database prod
blue-data --json source query mydb "SELECT status, COUNT(*) FROM orders GROUP BY status" --database prod
```

#### `source inspect`

Drill into any level of the hierarchy by passing 1–5 positional arguments:

```bash
blue-data source inspect mydb                                  # source
blue-data source inspect mydb prod                             # database
blue-data source inspect mydb prod public                      # collection
blue-data source inspect mydb prod public orders               # entity
blue-data source inspect mydb prod public orders total         # attribute
```

With `--json` for full records:

```bash
blue-data --json source inspect mydb prod public orders | jq .record.properties
```

---

### `search`

Hybrid BM25 + vector search across all registry records.

```bash
blue-data search "customer email"
blue-data search "orders" --type entity --limit 5
blue-data --json search "total revenue" | jq '.[].name'
```

---

## Typical workflow

```bash
# 1. Register a source (or use BLUE_DATA_SOURCES_CONFIG)
blue-data source add shop --type sqlite --database-dir /data/shop

# 2. Sync structure, collect stats, enrich
blue-data source sync shop
blue-data source stats shop
blue-data source enrich shop
blue-data source metadata shop

# 3. Explore
blue-data search "revenue"
blue-data source inspect shop prod public
blue-data source inspect shop prod public orders
```

## Running tests

```bash
cd platform/cli
python3 -m pytest tests/ -v
```
