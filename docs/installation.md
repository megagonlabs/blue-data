# Installation

## Components

`blue-data` is organized into a core library (`lib/`) and platform components (`platform/`). Install `lib` first — all platform components depend on it.

Each component has a `scripts/` directory. Run scripts from the component's root directory.

| Script | Components | Purpose |
|---|---|---|
| `build.sh` | all | Build wheel + sdist into `dist/` |
| `install.sh` | all | Editable install (`python3 -m pip install -e .`) |
| `publish.sh` | lib only | Publish to package registry via twine |

**Editable install (development):**

```bash
cd lib && ./scripts/install.sh
cd platform/api && ./scripts/install.sh
cd platform/cli && ./scripts/install.sh
cd platform/json-mcp && ./scripts/install.sh
cd platform/registry-mcp && ./scripts/install.sh
```

**Build distributable packages:**

```bash
cd lib && ./scripts/build.sh
cd platform/api && ./scripts/build.sh
cd platform/cli && ./scripts/build.sh
cd platform/json-mcp && ./scripts/build.sh
cd platform/registry-mcp && ./scripts/build.sh
```

Requires the `build` package (`pip install build`).

---

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
| `chromadb` | `chromadb` | `ChromaDBVectorSource` |
| `bn` | `pgmpy`, `networkx` | `BayesianNetworkSource` |
| `parquet` | `pyarrow` | Parquet file source |
| `llm` | `anthropic` | LLM-augmented enrichment via `MetaData(llm_fn=...)` |

> **Redis Stack required:** `RedisJSONSource` and `RedisVectorSource` use `JSON.SET` and `FT.CREATE` commands that are not available in standard Redis. You need **Redis Stack** (`redis-stack-server`), not plain `redis`.

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
