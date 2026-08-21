# blue-data — Deployment & Ops

## Packages

`blue-data` ships as four separate installable artifacts:

| Artifact | PyPI name | Entry point |
|----------|-----------|-------------|
| Core library | `blue-data` | Python import |
| REST API | `blue-data-api` | `uvicorn registry_api.main:app` |
| Registry MCP | `blue-data-registry-mcp` | `blue-data-registry-mcp` |
| CLI | `blue-data-cli` | `blue-data` |

The JSON MCP (`platform/json-mcp/`) is a separate package (`blue-data-json-mcp`) intended for development and debugging — it is not required for production.

---

## External Dependencies

| Service | Required by | Notes |
|---------|------------|-------|
| Redis Stack | REST API, MCPs, CLI (when `BLUE_DATA_REGISTRY_STORE=redis`) | `redis/redis-stack-server:latest`; provides ReJSON and RediSearch modules; port 6379 |
| Redis Stack | Search index | Same Redis instance also stores the vector index used by `search_records`; requires RediSearch module |
| Anthropic API | MetaData enrichment (when `BLUE_DATA_LLM_PROVIDER=anthropic`) | `ANTHROPIC_API_KEY`; `claude-opus-4-8` default model |
| OpenAI API | MetaData enrichment (when `BLUE_DATA_LLM_PROVIDER=openai`) | `OPENAI_API_KEY`; `gpt-4o` default model |

Redis is fully optional — `BLUE_DATA_REGISTRY_STORE=memory` runs entirely in-process with no external services. The file backend (`BLUE_DATA_REGISTRY_STORE=file`) survives restarts without Redis but does not support vector search.

LLM enrichment is also optional — `enrich_source_metadata` runs deterministic-only enrichment (semantic roles, VST classifications) when no `BLUE_DATA_LLM_PROVIDER` is set.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BLUE_DATA_REGISTRY_STORE` | No | `memory` | Registry backend: `memory`, `redis`, or `file` |
| `BLUE_DATA_REGISTRY_REDIS_URL` | When `STORE=redis` | `redis://localhost:6379/0` | Redis connection URL |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | No | `blue_data` | Key prefix in Redis — allows multiple registry instances on the same Redis |
| `BLUE_DATA_REGISTRY_FILE` | When `STORE=file` | `blue_data_store.json` | File path for the file backend |
| `BLUE_DATA_REGISTRY_VECTOR_DIM` | No | `1536` | Embedding vector dimension for the search index |
| `BLUE_DATA_LLM_PROVIDER` | No | — | `anthropic` or `openai`; omit for deterministic-only enrichment |
| `BLUE_DATA_LLM_MODEL` | No | `claude-opus-4-8` / `gpt-4o` | LLM model for MetaData enrichment; default depends on provider |
| `ANTHROPIC_API_KEY` | When `LLM_PROVIDER=anthropic` | — | Anthropic API key |
| `OPENAI_API_KEY` | When `LLM_PROVIDER=openai` | — | OpenAI API key |
| `BLUE_DATA_SOURCES_CONFIG` | No | — | JSON file pre-loading data sources at startup |
| `BLUE_DATA_SOURCES_SYNC` | No | `true` | Auto-sync sources loaded from `SOURCES_CONFIG` |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT` | No | — | BM25 weight override in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT` | No | — | Vector weight override in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT` | No | — | Value-match weight override in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD` | No | — | Minimum BM25 score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD` | No | — | Minimum vector score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD` | No | — | Minimum combined score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL` | No | — | `1`/`true` to enable hierarchical score boosting |

All variables are read once at startup during singleton construction. Changing them requires a process restart.

---

## Running the REST API

### Development

```bash
cd platform/api
pip install -e ".[dev]"
BLUE_DATA_REGISTRY_STORE=redis BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \
  uvicorn registry_api.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -e "lib/" && pip install -e "platform/api/"
EXPOSE 8000
CMD ["uvicorn", "registry_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker run -p 8000:8000 \
  -e BLUE_DATA_REGISTRY_STORE=redis \
  -e BLUE_DATA_REGISTRY_REDIS_URL=redis://redis:6379/0 \
  -e BLUE_DATA_LLM_PROVIDER=anthropic \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  blue-data-api
```

### Redis Stack

```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

---

## Running the Registry MCP Server

The Registry MCP communicates over **stdio** — launched by the MCP host, not as a daemon.

```bash
# Direct (for testing)
BLUE_DATA_REGISTRY_STORE=redis BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \
  blue-data-registry-mcp
```

Claude Desktop config:

```json
{
    "mcpServers": {
        "blue-data-registry": {
            "command": "blue-data-registry-mcp",
            "env": {
                "BLUE_DATA_REGISTRY_STORE": "memory",
                "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json",
                "BLUE_DATA_LLM_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "sk-ant-..."
            }
        }
    }
}
```

---

## Running the JSON MCP Server

Also stdio. Intended for development and registry debugging, not production use.

```bash
BLUE_DATA_REGISTRY_STORE=redis BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \
  blue-data-json-mcp
```

---

## Running the CLI

```bash
pip install -e "lib/" -e "platform/cli/"

export BLUE_DATA_REGISTRY_STORE=redis
export BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0

blue-data sources add northwind --type sqlite --database-dir /data/sqlite
blue-data sync northwind
blue-data stats northwind
blue-data enrich northwind
blue-data metadata northwind
blue-data search "customer revenue"
blue-data inspect entity northwind northwind public orders
```

---

## Port Assignments

| Service | Port |
|---------|------|
| **blue-data REST API** | **8000** |
| blue-data-doc-source REST API | 8001 |
| blue-data-web-source REST API | 8002 |
| Redis Stack | 6379 |

---

## Source Config File

`BLUE_DATA_SOURCES_CONFIG` points to a JSON file that pre-loads sources at startup:

```json
{
    "sources": [
        {
            "name": "northwind",
            "type": "sqlite",
            "properties": {"connection": {"database_directory": "/data/sqlite"}}
        },
        {
            "name": "analytics",
            "type": "postgres",
            "properties": {
                "connection": {
                    "host": "pg.internal",
                    "port": 5432,
                    "database": "analytics",
                    "user": "reader",
                    "password": "secret"
                }
            }
        }
    ]
}
```

When `BLUE_DATA_SOURCES_SYNC=true` (the default), each source is synced recursively at startup. Set to `false` to skip sync and register sources without reading their live schema.

---

## Registry Store Backends

| Backend | `BLUE_DATA_REGISTRY_STORE` | Persistence | Vector search | Notes |
|---------|---------------------------|-------------|--------------|-------|
| `MemoryJSONSource` | `memory` | No | In-process (numpy) | Default; suitable for dev and testing |
| `FileJSONSource` | `file` | Yes | No | Survives restarts; no vector search |
| `RedisJSONSource` | `redis` | Yes | Yes (RediSearch) | Production; multi-process safe |

Vector search (`search_records`) requires either the memory backend (in-process numpy cosine) or the Redis backend (RediSearch KNN). The file backend does not support vector search.

---

## Observability

No OTEL or Prometheus instrumentation is wired in V1. Observability relies on:

- **Uvicorn access logs** — request/response logging from the ASGI server.
- **Startup log** — the REST API logs the resolved registry store type and search config at startup.
- **Error propagation** — unhandled exceptions return `500` with a detail message; `404` for missing sources or records.

Structured logging and metrics are planned for a future release.
