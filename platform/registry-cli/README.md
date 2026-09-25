# blue-registry CLI

`platform/registry-cli` is a command-line interface for blue-registry DataRegistry operations.

## Installation

```bash
cd platform/registry-cli
pip install -e ../../lib
pip install -e .
```

## Local storage

All CLI-owned state lives under `~/.blue-registry/`:

```
~/.blue-registry/
  .profiles              # named configuration profiles (INI, one section per profile)
  .selected.profile      # the currently-active profile name
  registry.json          # registry data when store=file (default path)
```

The directory and all files it contains are created automatically on first use.
Override the home directory with `BLUE_DATA_REGISTRY_HOME`.

## Profiles

Profiles associate a named set of configuration values (LLM keys, store backend, search
tuning, etc.) with a single identifier. Commands always use the selected profile unless
`--profile NAME` or `BLUE_DATA_PROFILE` overrides it.

```bash
# First-time setup — configure the default profile
blue-registry profile config

# Add a second profile for a different environment
blue-registry profile add prod
blue-registry profile config --profile prod

# Switch between profiles
blue-registry profile select prod
blue-registry profile select default

# Inspect what is active
blue-registry profile list
blue-registry profile inspect
```

`profile config` with no arguments walks through every required parameter interactively.
`profile config PARAM VALUE` sets a single value directly (secrets always prompt, never
accept a command-line value). Enter `$VAR` at any prompt to store an environment variable
reference rather than a literal value.

### Secrets

Secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) are stored in one of two forms:

```
# Encoded literal — stored in ~/.blue-registry/.profiles
$ blue-registry profile config OPENAI_API_KEY
  value: sk-svcacct-...        # stored as enc:<base64> in ~/.blue-registry/.profiles

# Environment variable reference — value never touches disk
$ blue-registry profile config OPENAI_API_KEY
  value: $OPENAI_API_KEY       # stored as $OPENAI_API_KEY; read from the environment at use
```

`blue-registry profile inspect` masks stored secrets and shows references by name with
their resolution state (`$OPENAI_API_KEY (set)` or `$OPENAI_API_KEY (unset)`), so you
can see what to export without revealing anything.

> **The encoded form is obfuscation, not encryption** — it keeps a key off your screen
> and out of a careless `grep`, and anyone who can read the file can decode it.
> The `0600` file mode is the real protection. Where that is not enough, use the `$VAR`
> reference form so the secret never touches disk.

## Configuration

All parameters can be set in a profile. The full list, with defaults:

| Parameter | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(unset)_ | OpenAI API key |
| `ANTHROPIC_API_KEY` | _(unset)_ | Anthropic API key |
| `BLUE_DATA_LLM_PROVIDER` | `openai` | LLM provider (`openai` or `anthropic`) |
| `BLUE_DATA_LLM_MODEL` | `gpt-4o` | Default LLM model |
| `BLUE_DATA_CLI_FORMAT` | `table` | Output format (`table`, `json`, or `nl`) |
| `BLUE_DATA_REGISTRY_STORE` | `memory` | Registry backend (`memory`, `file`, or `redis`) |
| `BLUE_DATA_REGISTRY_FILE` | `~/.blue-registry/registry.json` | Path to registry JSON file (store=file) |
| `BLUE_DATA_REGISTRY_REDIS_URL` | _(unset)_ | Redis URL (store=redis) |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Redis key namespace |
| `BLUE_DATA_SOURCES_CONFIG` | _(unset)_ | Path to sources config JSON file |
| `BLUE_DATA_SOURCES_SYNC` | `true` | Sync sources on startup from sources config |
| `BLUE_DATA_REGISTRY_METADATA_LLM_MODEL` | _(inherits `BLUE_DATA_LLM_MODEL`)_ | Model override for `source metadata` |
| `BLUE_DATA_REGISTRY_VECTOR_DIM` | `1536` | Embedding dimensions (must match embedding model) |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT` | _(library default)_ | BM25 weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT` | _(library default)_ | Vector weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT` | _(library default)_ | Value weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD` | _(library default)_ | Minimum BM25 score |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD` | _(library default)_ | Minimum vector score |
| `BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD` | _(library default)_ | Minimum combined score |
| `BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL` | _(library default)_ | Enable hierarchical search boosting |

Precedence: command-line flag → environment variable → profile value → default.

## Source config file

Pre-load sources at startup via `BLUE_DATA_SOURCES_CONFIG`:

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
blue-registry source list
```

#### `source add`

```bash
blue-registry source add NAME --type sqlite --database-dir /path/to/dbs
BLUE_REGISTRY_SOURCE_PASSWORD=secret blue-registry source add NAME --type postgres --host localhost --db-name mydb --user app
```

#### `source remove`

```bash
blue-registry source remove NAME
```

#### `source sync`

Walk the live source and register all databases, collections, entities, and attributes.

```bash
blue-registry source sync mydb                    # recursive by default
blue-registry source sync mydb --no-recursive     # top-level only
```

#### `source stats`

Collect row counts, null rates, and value statistics from the live source.

```bash
blue-registry source stats mydb
blue-registry source stats mydb --no-recursive
```

#### `source enrich`

Run deterministic semantic type inference (BOOLEAN, INTEGER, EMAIL, UUID, etc.) on all attributes.

```bash
blue-registry source enrich mydb
```

#### `source metadata`

Run the full MetaData enrichment pipeline (semantic roles, VST, process semantics, semantic links,
and LLM-augmented enrichment when a provider is configured).

```bash
blue-registry source metadata mydb
blue-registry source metadata mydb --rebuild      # overwrite existing enrichment
```

#### `source query`

Execute raw SQL against a live source:

```bash
blue-registry source query mydb "SELECT * FROM orders LIMIT 5" --database prod
blue-registry --format json source query mydb "SELECT status, COUNT(*) FROM orders GROUP BY status" --database prod
```

#### `source inspect`

Drill into any level of the hierarchy by passing 1–5 positional arguments:

```bash
blue-registry source inspect mydb                                  # source
blue-registry source inspect mydb prod                             # database
blue-registry source inspect mydb prod public                      # collection
blue-registry source inspect mydb prod public orders               # entity
blue-registry source inspect mydb prod public orders total         # attribute
```

With `--format json` for full records:

```bash
blue-registry --format json source inspect mydb prod public orders | jq .record.properties
```

---

### `search`

Hybrid BM25 + vector search across all registry records.

```bash
blue-registry search "customer email"
blue-registry search "orders" --type entity --limit 5
blue-registry --format json search "total revenue" | jq '.[].name'
```

---

## Typical workflow

```bash
# 1. Configure a profile (first time)
blue-registry profile config

# 2. Register a source (or use BLUE_DATA_SOURCES_CONFIG)
blue-registry source add shop --type sqlite --database-dir /data/shop

# 3. Sync structure, collect stats, enrich
blue-registry source sync shop
blue-registry source stats shop
blue-registry source enrich shop
blue-registry source metadata shop

# 4. Explore
blue-registry search "revenue"
blue-registry source inspect shop prod public
blue-registry source inspect shop prod public orders
```

## Running tests

```bash
cd platform/registry-cli
python3 -m pytest tests/ -v
```
