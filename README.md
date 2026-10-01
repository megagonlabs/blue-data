# blue-data

A data intelligence layer that makes heterogeneous enterprise data understandable to AI agents and language models.

LLMs querying enterprise data fail in silent, predictable ways — they guess coded values, miss what columns actually mean, and never see the data-quality problems that make a syntactically correct query return a wrong answer. `blue-data` sits between raw data sources and the AI layer, enriching schemas with the semantic metadata — coded values, natural-language descriptions, data-quality signals, and process semantics — that lets agents discover, reason about, and query data correctly.

→ **[Full documentation](docs/README.md)** · **[Quick start](docs/quickstart.md)** · **[Installation](docs/installation.md)** · **[Examples](examples/README.md)** · **[CLI](docs/cli.md)** · **[MCP server](docs/registry-mcp.md)**

---

## What it does

- **Register** heterogeneous data sources — SQL, document, graph, vector, stream, and file — behind one consistent interface, and mirror their structure as a searchable catalog.
- **Enrich** schemas with semantic metadata: coded-value detection, natural-language column descriptions, semantic types, and process/temporal semantics — cheaply, mostly without LLM calls.
- **Discover** the right data by meaning with hybrid BM25 + vector search, so *"shipping cost"* finds `orders.freight`.
- **Profile** data quality before querying — outliers, disguised missing values, representation fragmentation, suspected typos — stored as registry properties agents can act on.
- **Query** sources in natural language, grounded in the enriched schema, as a one-shot translation or a multi-turn tool loop.
- **Serve** all of this through a REST API, a CLI, and MCP servers for Claude and other agents.

Full feature list: [docs/features.md](docs/features.md). Runnable demos: [examples/](examples/README.md). Demo datasets: [data/](data/README.md).

---

## Repository layout

```
blue-data/
├── lib/                      # Core Python library (blue-data)
│   ├── src/blue_data/        # DataRegistry, DataSource adapters, enrichment, search
│   └── tests/                # unit, integration, and benchmark tests
├── platform/
│   ├── registry-api/         # FastAPI REST service (port 8000) — `blue-data-api`
│   ├── registry-cli/         # `blue-registry` command-line interface
│   ├── registry-mcp/         # MCP server for registry operations (Claude Desktop / Claude Code)
│   └── json-mcp/             # MCP server for raw JSONSource key/value operations
├── docs/                     # Documentation
├── examples/                 # Runnable example scripts with captured output
├── design/                   # Architecture decision records
├── data/                     # Demo datasets (Northwind, Czech banking, finance, BIRD)
└── example.envrc             # Sample environment configuration (copy to .envrc)
```

---

## Requirements

- Python 3.10+
- Runtime dependencies `pandas`, `numpy`, `jsonpath-ng` — installed automatically; no build step.
- Optional: Redis Stack (`redis-stack-server`) for production registry persistence and vector search.
- Optional: an LLM API key for metadata enrichment and natural-language queries (deterministic enrichment needs none):

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or
export OPENAI_API_KEY=sk-...
```

Optional extras (`[postgres]`, `[mysql]`, `[mongodb]`, `[neo4j]`, `[redis]`, `[chromadb]`, `[bn]`, `[parquet]`, `[llm]`, `[all]`) are documented in [docs/installation.md](docs/installation.md). Full configuration — store backends, LLM providers, search tuning, and profiles — is in [docs/configuration.md](docs/configuration.md).

---

## Quick start

```bash
bash lib/scripts/install.sh          # editable install of blue-data (with dev extras)

# Minimal end-to-end — build a tiny SQLite DB, register it, sync, and search. No API key needed:
python3 - <<'PY'
import os, sqlite3, tempfile
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

d = tempfile.mkdtemp()
con = sqlite3.connect(os.path.join(d, "shop.db"))
con.executescript("CREATE TABLE customers(id INTEGER PRIMARY KEY, company_name TEXT, country TEXT);")
con.commit(); con.close()

reg = DataRegistry()
reg.register_source(SQLiteDBSource(name="shop", properties={"connection": {"database_directory": d}}))
reg.sync_source("shop", recursive=True)
print("entities:", [e["name"] for e in reg.list_collection_entities("shop", "shop", "public")])
print("search  :", [r["name"] for r in reg.search_records("customers")])
PY
```

For the full walkthrough — stats collection, LLM enrichment, hybrid search, and natural-language queries — see [docs/quickstart.md](docs/quickstart.md).

---

## Packages

| Package | Description |
|---|---|
| [`lib/`](lib/README.md) | Core library `blue-data` — `DataRegistry`, `DataSource` adapters, enrichment, and search. Install: `bash lib/scripts/install.sh` |
| [`platform/registry-api/`](platform/registry-api/README.md) | FastAPI REST service on port 8000, command `blue-data-api`. Install: `pip install -e platform/registry-api` |
| [`platform/registry-cli/`](platform/registry-cli/README.md) | Command-line interface `blue-registry` over the core ops. Install: `pip install -e platform/registry-cli` |
| [`platform/registry-mcp/`](platform/registry-mcp/README.md) | MCP server exposing registry ops as AI-callable tools, command `blue-data-registry-mcp`. Install: `pip install -e platform/registry-mcp` |
| [`platform/json-mcp/`](platform/json-mcp/README.md) | MCP server for raw JSONSource key/value operations, command `blue-data-json-mcp`. Install: `pip install -e platform/json-mcp` |
