# blue-data REST API

`platform/registry-api` exposes DataRegistry operations over HTTP via FastAPI.

## Installation & running

```bash
cd platform/registry-api
pip install -e ../../lib
pip install -e .

# dev (auto-reload)
uvicorn registry_api.main:app --reload --port 8000

# or via the installed script
blue-data-api
```

The interactive docs are available at `http://localhost:8000/docs` once the server is running.

## Environment variables

The registry/LLM variables match `registry-mcp`; the `BLUE_DATA_API_*` variables below are specific to this REST service:

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_API_KEY` | _(none)_ | API key required for data endpoints. When unset, those endpoints return 401 unless `BLUE_DATA_API_AUTH_DISABLED=true` (see [Authentication](#authentication)) |
| `BLUE_DATA_API_AUTH_DISABLED` | `false` | Set `true` to disable auth (local/dev only) |
| `BLUE_DATA_API_HOST` | `127.0.0.1` | Bind address for `blue-data-api` (loopback by default) |
| `BLUE_DATA_API_PORT` | `8000` | Bind port for `blue-data-api` |
| `BLUE_DATA_API_ALLOW_WRITES` | `false` | Set `true` to allow `commit=true` on `POST /{source}/query` |
| `BLUE_DATA_REGISTRY_STORE` | `memory` | `memory`, `file`, or `redis` |
| `BLUE_DATA_REGISTRY_FILE` | `blue_data_store.json` | Path to registry JSON file (when store=file) |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (when store=redis) |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key prefix for Redis |
| `BLUE_DATA_LLM_PROVIDER` | _(none)_ | `anthropic` or `openai`; blank = deterministic-only (no LLM enrichment) |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when `BLUE_DATA_LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | _(none)_ | Required when `BLUE_DATA_LLM_PROVIDER=openai` |
| `BLUE_DATA_LLM_MODEL` | _(none)_ | Model ID; blank resolves per provider (`claude-opus-4-8` / `gpt-4o`) |
| `BLUE_DATA_SOURCES_CONFIG` | _(none)_ | Path to JSON source config file |

### Authentication

Data endpoints require an API key by default (health and docs — `/health`, `/docs`, `/redoc`, `/openapi.json` — are always open). Set a key and send it with each request as `X-API-Key` or `Authorization: Bearer`:

```bash
export BLUE_DATA_API_KEY=changeme
curl -H "X-API-Key: $BLUE_DATA_API_KEY" http://localhost:8000/search?q=orders
curl -H "Authorization: Bearer $BLUE_DATA_API_KEY" http://localhost:8000/search?q=orders
```

For local development you can disable auth entirely (every endpoint open):

```bash
export BLUE_DATA_API_AUTH_DISABLED=true
```

State-changing requests (`POST`/`PUT`/`DELETE`) must send `Content-Type: application/json` (a CSRF guard rejects form/text bodies with 415), and `commit=true` on `POST /{source}/query` also requires `BLUE_DATA_API_ALLOW_WRITES=true`.

## Source config file

Pre-load sources at startup by pointing `BLUE_DATA_SOURCES_CONFIG` at a JSON file:

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
| `GET` | `/search?q=<query>` | Hybrid BM25 + vector search; optional `?type=`, `?scope=`, `?page=` (default 0), `?page_size=` (default 10) |
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
| `PUT` | `/{source}/sync` | Sync source structure from live data source; optional `?recursive=true` (default: true) |
| `PUT` | `/{source}/stats` | Collect stats from live source; optional `?recursive=true` (default: true) |
| `PUT` | `/{source}/enrich` | Run semantic type inference on all attributes |
| `PUT` | `/{source}/metadata` | Run MetaData enrichment pipeline; optional `?recursive=true` (default: true), `?rebuild=false` |
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

### Relations

| Method | Path | Description |
|---|---|---|
| `GET` | `.../relation/{rel}` | Get relation record |
| `PUT` | `.../relation/{rel}/sync` | Sync relation |
| `PUT` | `.../relation/{rel}/stats` | Collect relation stats |

---

## Typical workflow

```bash
BASE=http://localhost:8000
# Send the API key on every data call (or export BLUE_DATA_API_AUTH_DISABLED=true for local use).
AUTH=(-H "X-API-Key: $BLUE_DATA_API_KEY")

# 1. Sync a source that was pre-loaded via BLUE_DATA_SOURCES_CONFIG
curl "${AUTH[@]}" -X PUT $BASE/mydb/sync

# 2. Collect stats
curl "${AUTH[@]}" -X PUT $BASE/mydb/stats

# 3. Run enrichment
curl "${AUTH[@]}" -X PUT $BASE/mydb/enrich
curl "${AUTH[@]}" -X PUT $BASE/mydb/metadata

# 4. Search
curl "${AUTH[@]}" "$BASE/search?q=customer+email"

# 5. Inspect an entity
curl "${AUTH[@]}" $BASE/mydb/database/prod/collection/public/entity/customers
```

## Running tests

```bash
cd platform/registry-api
python3 -m pytest tests/ -v
```
