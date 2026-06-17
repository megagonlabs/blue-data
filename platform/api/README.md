# blue-data REST API

`platform/api` exposes DataRegistry operations over HTTP via FastAPI.

## Installation & running

```bash
cd platform/api
pip install -e ../../lib
pip install -e .

# dev (auto-reload)
uvicorn registry_api.main:app --reload --port 8000

# or via the installed script
blue-data-api
```

The interactive docs are available at `http://localhost:8000/docs` once the server is running.

## Environment variables

Same set as `registry-mcp`:

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_STORE` | `memory` | `memory` or `redis` |
| `BLUE_DATA_REDIS_URL` | `redis://localhost:6379` | Redis connection URL (when store=redis) |
| `BLUE_DATA_REDIS_NAMESPACE` | `blue-data` | Key prefix for Redis |
| `BLUE_DATA_LLM_PROVIDER` | _(none)_ | `anthropic` to enable LLM enrichment |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when LLM provider is anthropic |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` | Model ID for LLM enrichment |
| `BLUE_DATA_CONFIG` | _(none)_ | Path to JSON source config file |

## Source config file

Pre-load sources at startup by pointing `BLUE_DATA_CONFIG` at a JSON file:

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

## Response envelope

All endpoints wrap their payload:

| Shape | Used for |
|---|---|
| `{"result": {...}}` | Single record or object |
| `{"results": [...]}` | Lists |
| `{"message": "Success"}` | Mutations with no return value |

Errors use standard HTTP status codes with a `{"detail": "..."}` body.

---

## Endpoints

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `{"status": "ok"}` |

### Records

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | List all records; optional `?type=` and `?scope=` filters |
| `GET` | `/search?q=<query>` | Hybrid BM25 + vector search; optional `?type=` filter |
| `GET` | `/record?name=&type=&scope=` | Get one record by identity triple |

### Sources

| Method | Path | Description |
|---|---|---|
| `GET` | `/sources` | List registered source names |
| `GET` | `/{source}` | Get source registry record |
| `DELETE` | `/{source}` | Deregister source |
| `GET` | `/{source}/properties` | List all source properties |
| `GET` | `/{source}/property/{key}` | Get one property |
| `POST` | `/{source}/property/{key}` | Set a property |
| `DELETE` | `/{source}/property/{key}` | Delete a property |
| `GET` | `/{source}/databases` | List registered databases |
| `PUT` | `/{source}/sync` | Sync source structure from live data source |
| `PUT` | `/{source}/stats` | Collect stats from live source |
| `PUT` | `/{source}/enrich` | Run semantic type inference on all attributes |
| `PUT` | `/{source}/metadata` | Run MetaData enrichment pipeline; optional `?rebuild=true` |
| `POST` | `/{source}/connect` | Connect and inspect live source tree |
| `POST` | `/{source}/query` | Execute a query; body: `{"query": "...", "database": "..."}` |

### Databases

| Method | Path | Description |
|---|---|---|
| `GET` | `/{source}/database/{db}` | Get database record |
| `POST` | `/{source}/database/{db}` | Register a database |
| `PUT` | `/{source}/database/{db}` | Update description/properties; optional `?sync=true` |
| `DELETE` | `/{source}/database/{db}` | Deregister database |
| `GET` | `/{source}/database/{db}/collections` | List collections |
| `PUT` | `/{source}/database/{db}/sync` | Sync database |
| `PUT` | `/{source}/database/{db}/stats` | Collect database stats |

### Collections

| Method | Path | Description |
|---|---|---|
| `GET` | `/{source}/database/{db}/collection/{col}` | Get collection record |
| `POST` | `/{source}/database/{db}/collection/{col}` | Register collection |
| `PUT` | `/{source}/database/{db}/collection/{col}` | Update collection |
| `DELETE` | `/{source}/database/{db}/collection/{col}` | Deregister collection |
| `GET` | `/{source}/database/{db}/collection/{col}/entities` | List entities |
| `GET` | `/{source}/database/{db}/collection/{col}/relations` | List relations |
| `PUT` | `/{source}/database/{db}/collection/{col}/sync` | Sync collection |
| `PUT` | `/{source}/database/{db}/collection/{col}/stats` | Collect collection stats |
| `PUT` | `/{source}/database/{db}/collection/{col}/metadata` | Run metadata enrichment |

### Entities

| Method | Path | Description |
|---|---|---|
| `GET` | `.../entity/{entity}` | Get entity record |
| `POST` | `.../entity/{entity}` | Register entity |
| `PUT` | `.../entity/{entity}` | Update entity |
| `DELETE` | `.../entity/{entity}` | Deregister entity |
| `GET` | `.../entity/{entity}/attributes` | List attributes |
| `PUT` | `.../entity/{entity}/sync` | Sync entity |
| `PUT` | `.../entity/{entity}/stats` | Collect entity stats |
| `PUT` | `.../entity/{entity}/metadata` | Run metadata enrichment |

### Attributes

| Method | Path | Description |
|---|---|---|
| `GET` | `.../attribute/{attr}` | Get attribute record |
| `PUT` | `.../attribute/{attr}` | Update attribute |
| `DELETE` | `.../attribute/{attr}` | Deregister attribute |
| `PUT` | `.../attribute/{attr}/stats` | Collect attribute stats |
| `PUT` | `.../attribute/{attr}/metadata` | Run metadata enrichment |

---

## Typical workflow

```bash
BASE=http://localhost:8000

# 1. Sync a source that was pre-loaded via BLUE_DATA_CONFIG
curl -X PUT $BASE/mydb/sync

# 2. Collect stats
curl -X PUT $BASE/mydb/stats

# 3. Run enrichment
curl -X PUT $BASE/mydb/enrich
curl -X PUT $BASE/mydb/metadata

# 4. Search
curl "$BASE/search?q=customer+email"

# 5. Inspect an entity
curl $BASE/mydb/database/prod/collection/public/entity/customers
```

## Running tests

```bash
cd platform/api
python3 -m pytest tests/ -v
```
