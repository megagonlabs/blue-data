# blue-data — Software Stack

---

## Language & Runtime

| Concern | Choice |
|---------|--------|
| Language | Python |
| Minimum version | 3.10 |
| Package manager | pip |
| Project config | `pyproject.toml` |

---

## Core Dependencies (always installed)

| Package | Purpose |
|---------|---------|
| `pandas` | DataFrame return type for `execute_query` in SQL and file sources |
| `numpy` | Vector arithmetic in `MemoryVectorSource` (cosine similarity via dot product / norm) |
| `jsonpath-ng` | JSONPath expressions used in `FileJSONSource` path resolution |

These three are the only hard dependencies — `blue-data` installs and runs with no external services.

---

## Storage Backends (optional extras)

### JSONSource backends

| Extra | Package | Backend |
|-------|---------|---------|
| `[redis]` | `redis` | `RedisJSONSource` — uses RedisJSON (`JSON.SET`/`JSON.GET`); requires Redis Stack |
| `[mongodb]` | `pymongo` | `MongoDBJSONSource` |

### VectorSource backends

| Extra | Package | Backend |
|-------|---------|---------|
| `[redis]` | `redis` | `RedisVectorSource` — uses RediSearch KNN (`FT.SEARCH`); requires Redis Stack |
| `[chromadb]` | `chromadb` | `ChromaDBVectorSource` |

`MemoryVectorSource` and `FileVectorSource` are built-in and require no extra — they use `numpy`.

### SQL DataSources

| Extra | Package | Backend |
|-------|---------|---------|
| `[postgres]` | `psycopg2-binary` | `PostgresDBSource` |
| `[mysql]` | `mysql-connector-python` | `MySQLDBSource` |

`SQLiteDBSource` is built-in — `sqlite3` is in the Python standard library.

### Graph DataSources

| Extra | Package | Backend |
|-------|---------|---------|
| `[neo4j]` | `neo4j` | `Neo4JGraphSource` |

`MemoryGraphSource` and `FileGraphSource` are built-in.

### Probabilistic DataSources

| Extra | Package | Backend |
|-------|---------|---------|
| `[bn]` | `pgmpy`, `networkx` | `BayesianNetworkSource` |

### Columnar / File

| Extra | Package | Purpose |
|-------|---------|---------|
| `[parquet]` | `pyarrow` | Parquet file support in `FileSource` |

### LLM Integration

| Extra | Package | Purpose |
|-------|---------|---------|
| `[llm]` | `anthropic` | `MetadataEnricher` (enrichment pipeline); `execute_query_nl_tools` (tool loop) |

`anthropic` is deferred-imported in the enrichment and NL tool code — the library works without it when LLM features are not used. `ANTHROPIC_API_KEY` is read by the SDK automatically.

**Note:** `openai` is declared in the `api` platform's `[llm]` extra, not in the lib — it is used for embedding generation in the REST API deployment, not in the core library.

---

## Registry / Search

The Registry and DataRegistry do not require any external services when using the default `MemoryJSONSource` + `MemoryVectorSource` backends. BM25 keyword search is implemented in pure Python using `keyword_search.py` (TF-IDF variant) — no search library dependency.

Hybrid search fuses BM25 scores and vector similarity scores using a configurable weighted sum in `ranking.py`. All math is `numpy`.

---

## External Interfaces

### REST API (`platform/api/`)

| Concern | Choice |
|---------|--------|
| Framework | FastAPI (`fastapi[standard]>=0.100.0`) |
| ASGI server | Uvicorn (included via `fastapi[standard]`) |
| Port | 8000 |

Routes are split across three routers: `records` (search, health, registry CRUD), `sources` (database/collection/entity inspection), `hierarchy` (path-based traversal). Request/response models are Pydantic `BaseModel`. No business logic in route handlers.

### CLI (`platform/cli/`)

| Concern | Choice |
|---------|--------|
| Argument parsing | Click |
| Output | plain text (default) or JSON (`--json` flag) |

Command groups: `source` (list, add, remove, sync, stats, enrich, metadata, query, inspect), `search`. All delegate to `DataRegistry` via the `config.py` singleton.

### MCP Servers (`platform/registry-mcp/`, `platform/json-mcp/`)

| Concern | Choice |
|---------|--------|
| Library | `mcp` / `fastmcp` |
| Transport | stdio (default for Claude Desktop) |

`registry-mcp` exposes registry discovery and search operations. `json-mcp` exposes raw JSONSource get/set/delete operations. Both use a `DataRegistry` singleton from the shared `config.py`.

---

## Testing

| Concern | Choice |
|---------|--------|
| Test runner | `pytest` (lib); `pytest` + `httpx` (api) |
| Async mode | `asyncio_mode = "auto"` (pytest-asyncio) |
| Coverage | `pytest-cov` |

All tools are declared as `dev` dependencies in `lib/pyproject.toml`. Unit tests use `MemoryJSONSource`, `MemoryVectorSource`, and `MagicMock` to avoid external services. Integration tests require real external services and are excluded from the default `testpaths = ["tests/unit"]`.

---

## Dependency Summary

| Package | Version | Extra | Role |
|---------|---------|-------|------|
| `pandas` | latest | always | DataFrame return for SQL/file queries |
| `numpy` | latest | always | Cosine similarity; BM25 vector ops |
| `jsonpath-ng` | latest | always | JSONPath resolution in FileJSONSource |
| `psycopg2-binary` | latest | `[postgres]` | PostgreSQL adapter |
| `mysql-connector-python` | latest | `[mysql]` | MySQL adapter |
| `pymongo` | latest | `[mongodb]` | MongoDB adapter |
| `neo4j` | latest | `[neo4j]` | Neo4j Bolt driver |
| `redis` | latest | `[redis]` | RedisJSON + RediSearch (Redis Stack) |
| `chromadb` | latest | `[chromadb]` | ChromaDB vector store |
| `pgmpy` | latest | `[bn]` | Bayesian network inference |
| `networkx` | latest | `[bn]` | Graph representation for BN |
| `pyarrow` | latest | `[parquet]` | Parquet file I/O |
| `anthropic` | latest | `[llm]` | MetadataEnricher; execute_query_nl_tools |
| `fastapi[standard]` | ≥0.100.0 | `platform/api` | REST API framework + uvicorn |
| `click` | latest | `platform/cli` | CLI argument parsing |
| `pytest` | latest | `dev` | Test runner |
| `pytest-cov` | latest | `dev` | Coverage measurement |
| `httpx` | latest | `platform/api dev` | FastAPI TestClient HTTP transport |
