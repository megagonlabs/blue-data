# blue-data

blue-data is a data intelligence layer for AI applications. It provides a unified interface to register, introspect, and query heterogeneous data sources such as SQL databases, document stores, and graph databases — and enriches them with semantic metadata that makes data understandable to AI agents and language models. It sits between raw data and the AI layer, answering questions like: what data exists, what it means, how it relates, and how it can safely be queried.

Its core capabilities include:

- **Unified access** across heterogeneous enterprise data sources
- **Deep data discoverability** to identify the most relevant data for a given task
- **Fine-grained semantic understanding** of schemas, tables, columns, relationships, business semantics, and values
- **Task-aware intelligence** to determine whether available data is sufficient and appropriate to accomplish a specific task
- **Cross-source intelligence** that understands relationships and semantics across multiple enterprise systems
- **AI-ready semantic metadata** that enables more accurate reasoning, planning, and decision-making over enterprise data

→ **[Full feature list](docs/features.md)** · **[Installation](docs/installation.md)** · **[Quick start](docs/quickstart.md)** · **[Docs](docs/README.md)** · **[Examples](#examples)**

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


## Concepts

**DataSource** — an adapter for an external data store (SQLite, Postgres, Redis, etc.). Each source exposes a consistent interface for listing databases, collections, entities, relations, and executing queries.

**DataRegistry** — a catalog that tracks registered sources and mirrors their structure (databases → collections → entities → attributes) as addressable records. Records carry metadata, descriptions, properties, statistics, and are searchable.

**JSONSource** — the storage backend for the registry itself. Defaults to in-memory (`MemoryJSONSource`) for development; `RedisJSONSource` is the production backend.

**VectorSource** — pluggable vector index used by the search engine. `MemoryVectorSource` for dev/test; `RedisVectorSource` for production (requires Redis Stack).

## Repository layout

```
blue-data/
├── lib/                          # Python library (blue-data)
│   ├── src/blue_data/
│   └── tests/
├── platform/
│   ├── api/                      # REST API (blue-data-api)
│   ├── cli/                      # Command-line interface (blue-data)
│   ├── json-mcp/                 # MCP server for JSONSource operations
│   └── registry-mcp/            # MCP server for registry operations
├── docs/                         # Documentation
├── data/                         # Demo datasets (Northwind, Czech banking, finance)
├── design/                       # Architecture decision records
└── examples/                     # Runnable examples
```

## Requirements

- Python 3.10+
- Runtime dependencies: `pandas`, `numpy` — no build step required
- Optional: Redis Stack (`redis-stack-server`) for production registry persistence and vector search
- Optional: Anthropic or OpenAI API key for LLM metadata enrichment

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

## Quick start

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry()
source = SQLiteDBSource(name="sqlite", properties={"connection": {"database_directory": "/tmp/my-data"}})
registry.register_source(source)

registry.sync_source("sqlite", recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source_metadata("sqlite", recursive=True)

results = registry.search_records("user accounts")
```

See **[docs/guide.md](docs/guide.md)** for the full usage guide — syncing, stats, enrichment, search, and natural language queries.

See **[docs/extending.md](docs/extending.md)** for implementing a new DataSource or custom NL translation.

## Examples

See **[examples/README.md](examples/README.md)** for the full list of runnable examples — scenario demos, feature demos, pipeline demos, integration demos, and benchmarks.

See **[data/README.md](data/README.md)** for the demo datasets (Northwind and Czech banking) used by the examples.

## Configuration

All platform components (API, CLI, MCP servers) are configured via environment variables. Copy `example.envrc` to `.envrc` and fill in your values — `.envrc` is gitignored and never committed.

```bash
cp example.envrc .envrc
source .envrc
```

Variables can also be set inline or exported in your shell. The sections below document every supported variable, its default, and when it is required.

### Profiles (`blue_data.utils.config`)

A CLI in this family does not have to make users export anything. `blue_data.utils.config` gives it named **profiles** — sets of these same variables, stored per CLI in `~/.<cli>/.profiles` — so switching environments is one command instead of a shell full of exports.

```python
from blue_data.utils.config import base_spec, build_resolver, load_spec

spec = base_spec().merged_with(load_spec("my_cli/profile_spec.json"))
resolver = build_resolver(spec, home="~/.mycli")
resolver.export()          # resolved values -> os.environ, for everything that reads them
```

`ProfileStore.initialize()` creates the `default` profile on first run, so a CLI needs no setup step before it works. A CLI declares its own parameters in a JSON spec and merges them with `base_spec()`, which holds the family-wide ones (`OPENAI_API_KEY`, `BLUE_DATA_LLM_MODEL`, `BLUE_DATA_CLI_FORMAT`, …). Each entry declares a `default`, a `prompt` shown during interactive configuration, whether it is `required` (which selects what a walkthrough asks about), and a `cast` — `directory`, `file`, `str`, `int`, `float`, `bool` or `secret`.

Resolution order is **command option > environment variable > profile > spec default**, and a parameter may `inherit` from others, so `MYCLI_EXTRACTION_LLM_MODEL` can fall back to `MYCLI_LLM_MODEL` and then to `BLUE_DATA_LLM_MODEL`.

Secret parameters are stored either encoded, or as a `$VAR` reference resolved from the environment at use. The profiles file is written `0600`, and nothing decodes a secret for display. The encoding is obfuscation rather than encryption — the file mode is the real protection, and the reference form is what keeps a secret off disk entirely.

This package is deliberately free of any CLI framework, so it adds no dependencies: it decides *what to ask for* and *what a value resolves to*, while prompting and command wiring stay in each CLI. `blue-data-kb-source`'s `kb profile` group is the reference implementation.

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

Supported source types: `sqlite`, `postgres`, `mysql`, `mongodb`, `neo4j`, `file`.

---

## Platform

The `platform/` directory contains deployable components built on top of `lib/`.

| Component | Description | Status |
|---|---|---|
| [`lib`](lib/README.md) | Core Python library — DataRegistry, DataSource, enrichment, search | ✅ Done |
| [`platform/registry-mcp`](platform/registry-mcp/README.md) | MCP server — exposes registry ops as tools for Claude and MCP clients | ✅ Done |
| [`platform/api`](platform/api/README.md) | REST API | ✅ Done |
| [`platform/cli`](platform/cli/README.md) | Command-line interface | ✅ Done |
| [`platform/json-mcp`](platform/json-mcp/README.md) | MCP server for raw JSONSource operations (memory + file) | ✅ Done |

### registry-mcp

```bash
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp
```

See [`docs/registry-mcp.md`](docs/registry-mcp.md) for Claude Desktop config, tool reference, and all options.

### api

```bash
blue-data-api  # http://localhost:8000 · interactive docs at /docs
```

See [`docs/api.md`](docs/api.md) for the full endpoint reference.

### cli

```bash
blue-data sources add mydb --type sqlite --database-dir /data
blue-data sync mydb && blue-data enrich mydb
blue-data search "revenue"
```

See [`docs/cli.md`](docs/cli.md) for the full command reference.

---

## Running tests

See **[docs/installation.md](docs/installation.md)** for the full test setup.
