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
`BLUE_DATA_STORE` and `BLUE_DATA_CONFIG` environment variables respectively.

## Environment variables

Same set as `registry-mcp` and `api`:

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_STORE` | `memory` | `memory` or `redis` |
| `BLUE_DATA_REDIS_URL` | `redis://localhost:6379/0` | Redis URL (when store=redis) |
| `BLUE_DATA_REDIS_NAMESPACE` | `blue_data` | Key prefix for Redis |
| `BLUE_DATA_LLM_PROVIDER` | _(none)_ | `anthropic` to enable LLM enrichment |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when LLM provider is anthropic |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` | Model ID for LLM enrichment |
| `BLUE_DATA_CONFIG` | _(none)_ | Path to JSON source config file |

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

### `sources`

```bash
blue-data sources list                              # list registered sources
blue-data sources add NAME --type sqlite --database-dir /path/to/dbs
blue-data sources add NAME --type postgres --host localhost --dbname mydb \
    --user app --password secret
blue-data sources remove NAME                       # deregister a source
```

### `sync`

Walk the live source and register all databases, collections, entities, and attributes.

```bash
blue-data sync mydb                    # recursive by default
blue-data sync mydb --no-recursive     # top-level only
```

### `stats`

Collect row counts, null rates, and value statistics from the live source.

```bash
blue-data stats mydb
```

### `enrich`

Run deterministic semantic type inference (BOOLEAN, INTEGER, EMAIL, UUID, etc.) on all attributes.

```bash
blue-data enrich mydb
```

### `metadata`

Run the full MetaData enrichment pipeline (semantic roles, VST, process semantics, semantic links,
and — when `BLUE_DATA_LLM_PROVIDER=anthropic` — LLM-augmented enrichment).

```bash
blue-data metadata mydb
blue-data metadata mydb --rebuild      # overwrite existing enrichment
```

### `search`

Hybrid BM25 + vector search across all registry records.

```bash
blue-data search "customer email"
blue-data search "orders" --type entity --limit 5
blue-data --json search "total revenue" | jq '.[].name'
```

### `inspect`

Drill into any level of the hierarchy:

```bash
blue-data inspect source mydb
blue-data inspect database mydb prod
blue-data inspect collection mydb prod public
blue-data inspect entity mydb prod public orders
blue-data inspect attribute mydb prod public orders total
```

With `--json` for full records:

```bash
blue-data --json inspect entity mydb prod public orders | jq .record.properties
```

### `query`

Execute raw SQL against a live source:

```bash
blue-data query mydb "SELECT * FROM orders LIMIT 5" --database prod
blue-data --json query mydb "SELECT status, COUNT(*) FROM orders GROUP BY status" --database prod
```

---

## Typical workflow

```bash
# 1. Register a source (or use BLUE_DATA_CONFIG)
blue-data sources add shop --type sqlite --database-dir /data/shop

# 2. Sync structure, collect stats, enrich
blue-data sync shop
blue-data stats shop
blue-data enrich shop
blue-data metadata shop

# 3. Explore
blue-data search "revenue"
blue-data inspect collection shop prod public
blue-data inspect entity shop prod public orders
```

## Running tests

```bash
cd platform/cli
python3 -m pytest tests/ -v
```
