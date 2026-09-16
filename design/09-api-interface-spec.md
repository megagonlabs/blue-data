# blue-data — API / Interface Spec

Four external interfaces sit above the core library: a Python library, a REST API, two MCP servers, and a CLI. No business logic belongs in any interface layer — all calls delegate to a `DataRegistry` singleton.

---

## 1. Python Library

The canonical interface. All other interfaces delegate to it.

### `DataRegistry`

Extends `Registry` and adds live source management, sync, stats collection, and enrichment.

```python
class DataRegistry(Registry):
    def __init__(
        self,
        store: JSONSource | None = None,        # default: MemoryJSONSource
        metadata_enricher: MetaData | None = None,
        hybrid_config: dict | None = None,
        vector_dim: int = 1536,
        _rebuild: bool | None = None,           # instance-level rebuild default
    ) -> None: ...
```

#### Source management

```python
def register_source(self, source: DataSource) -> None: ...
def deregister_source(self, source_name: str) -> None: ...
def get_source(self, source_name: str) -> DataSource | None: ...
def get_source_record(self, source_name: str) -> dict | None: ...
def list_sources(self) -> list[dict]: ...
def connect_source(self, source_name: str) -> DataSource | None: ...
    # Lazily constructs a DataSource from its stored connection properties
```

#### Source properties

```python
def get_source_properties(self, source_name: str) -> list[dict]: ...
def get_source_property(self, source_name: str, property_name: str) -> Any: ...
def set_source_property(self, source_name: str, property_name: str, value: Any, rebuild: bool | None = None) -> None: ...
def delete_source_property(self, source_name: str, property_name: str, rebuild: bool | None = None) -> None: ...
```

#### Hierarchy — databases

```python
def register_source_database(self, source: str, database: str, description: str = "", properties: dict = {}) -> None: ...
def update_source_database(self, source: str, database: str, description: str = "", properties: dict = {}) -> None: ...
def deregister_source_database(self, source: str, database: str) -> None: ...
def get_source_database(self, source: str, database: str) -> dict | None: ...
def list_source_databases(self, source: str) -> list[dict]: ...
def list_database_collections(self, source: str, database: str) -> list[dict]: ...
```

#### Hierarchy — collections, entities, attributes, relations

Same CRUD pattern at each level:
- `register_source_database_collection(source, database, collection, ...)` / `update_*` / `deregister_*` / `get_*`
- `register_source_database_collection_entity(source, database, collection, entity, ...)` / ...
- `register_source_database_collection_entity_attribute(source, database, collection, entity, attribute, ...)` / ...
- `list_database_collections`, `list_collection_entities`, `list_collection_relations`, `list_entity_attributes`

#### Sync and stats

```python
def sync_source(self, source_name: str, recursive: bool = True) -> None: ...
    # Walk live DataSource structure and reconcile registry records; idempotent

def sync_source_database(self, source: str, database: str, recursive: bool = True) -> None: ...
def sync_source_database_collection(self, source: str, database: str, collection: str) -> None: ...

def collect_source_stats(self, source_name: str, recursive: bool = True) -> None: ...
    # Gather row counts, sample values, min/max, nulls at all levels

def collect_source_database_stats(self, source: str, database: str) -> None: ...
def collect_source_database_collection_stats(self, source: str, database: str, collection: str) -> None: ...
def collect_source_database_collection_entity_stats(self, source: str, database: str, collection: str, entity: str) -> None: ...
def collect_source_database_collection_entity_attribute_stats(self, source: str, database: str, collection: str, entity: str, attribute: str) -> None: ...
```

#### Enrichment

```python
def enrich_source(self, source_name: str) -> None: ...
    # Run deterministic semantic type inference (INTEGER, FLOAT, DATE, EMAIL, ENUM_CATEGORY, ...)
    # Writes value_semantics to attribute.properties; requires stats to have run first

def enrich_source_metadata(self, source_name: str, recursive: bool = True, rebuild: bool = False) -> None: ...
    # Run full MetaData pipeline: semantic_role, quantitative VST, process_semantics,
    # semantic_links; LLM enrichment if BLUE_DATA_LLM_PROVIDER is set
    # rebuild=False is idempotent; rebuild=True overwrites existing enrichment
```

#### Search and query

```python
def search_records(
    self,
    query: str,
    type: str | None = None,
    scope: str | None = None,
    page: int = 0,
    page_size: int = 10,
) -> list[dict]: ...
    # Hybrid BM25 + vector search over all registry records

def get_record(self, name: str, record_type: str, scope: str = "") -> dict | None: ...
def list_records(self, record_type: str | None = None, scope: str | None = None) -> list[dict]: ...

def execute_query(
    self,
    source: str,
    query: str,
    database: str | None = None,
    collection: str | None = None,
    optional_properties: dict | None = None,
) -> list[dict]: ...
    # Execute a native query (e.g. SQL SELECT) against a live registered source

def import_data(
    self,
    source: str,
    target: str,
    collection: str = "default",
    database: str = "default",
    entity: str | None = None,
    mode: str = "append",
) -> dict: ...
    # Read from source, write to target; mode="overwrite" clears target first
```

---

## 2. REST API

Base URL: `http://localhost:8000`. Three routers handle records, sources, and the hierarchy. Handlers delegate to a `DataRegistry` singleton — no business logic in route functions.

### Records router (`/`)

#### `GET /health`

**Response** `200 OK`
```json
{"status": "ok"}
```

#### `GET /`

List all registry records, optionally filtered.

**Query params:** `type` (record type), `scope` (path prefix)

**Response** `200 OK`
```json
{"results": [...]}
```

#### `GET /search`

Hybrid BM25 + vector search over all registry records.

**Query params:** `q` (required), `type`, `scope`, `page`, `page_size` (default 10)

**Response** `200 OK`
```json
{"results": [...]}
```

#### `GET /record`

Get a specific record by identity.

**Query params:** `name` (required), `type` (required), `scope` (default `""`)

**Response** `200 OK` / `404`

---

### Sources router (`/{source_name}`)

#### `GET /sources`

List all registered source names.

#### `GET /{source_name}`

Get source record. **`404`** when not found.

#### `DELETE /{source_name}`

Deregister a source.

#### `GET /{source_name}/properties`

List all properties set on the source.

#### `GET /{source_name}/property/{property_name}`

Get a single source property value.

#### `POST /{source_name}/property/{property_name}`

Set a source property. Body: the raw value (any JSON type).

#### `DELETE /{source_name}/property/{property_name}`

Remove a source property.

#### `PUT /{source_name}/sync`

Sync registry records from the live source.

**Query param:** `recursive` (default `true`)

#### `PUT /{source_name}/stats`

Collect statistics from the live source.

**Query param:** `recursive` (default `true`)

#### `PUT /{source_name}/enrich`

Run deterministic semantic type inference on all attributes. Requires stats.

#### `PUT /{source_name}/metadata`

Run the full MetaData enrichment pipeline.

**Query params:** `recursive` (default `true`), `rebuild` (default `false`)

#### `POST /{source_name}/connect`

Lazily connect a source from its stored registry properties. Returns source type and database tree.

#### `POST /{source_name}/query`

Execute a native query against a live source.

**Body:** `{"query": "SELECT ...", "database": "...", "collection": "..."}`

**Response** `200 OK`
```json
{"results": [...]}
```

#### `GET /{source_name}/databases`

List databases registered under this source.

---

### Hierarchy router (`/{source_name}/database/{database_name}/...`)

CRUD pattern at each level. All paths follow:

```
/{source_name}/database/{database_name}
/{source_name}/database/{database_name}/collection/{collection_name}
/{source_name}/database/{database_name}/collection/{collection_name}/entity/{entity_name}
/{source_name}/database/{database_name}/collection/{collection_name}/entity/{entity_name}/attribute/{attribute_name}
/{source_name}/database/{database_name}/collection/{collection_name}/relation/{relation_name}
```

At each level the following operations exist (where applicable):

| Method | Path | Action |
|--------|------|--------|
| `GET` | `.../collections` | List collections under a database |
| `GET` | `.../entities` | List entities under a collection |
| `GET` | `.../relations` | List relations under a collection |
| `GET` | `.../attributes` | List attributes under an entity |
| `GET` | `.../{name}` | Get a specific record |
| `POST` | `.../{name}` | Register a new record |
| `PUT` | `.../{name}` | Update description / properties |
| `DELETE` | `.../{name}` | Deregister |
| `PUT` | `.../{name}/sync` | Sync from live source |
| `PUT` | `.../{name}/stats` | Collect stats |
| `PUT` | `.../{name}/metadata` | Run MetaData enrichment |

Request body for register/update: `{"description": "...", "properties": {...}}`

Response for all mutations: `{"message": "Success"}` or `{"detail": "..."}` on error.

---

## 3. MCP Servers

Two MCP servers are provided, both using **stdio** transport (fastmcp).

### Registry MCP (`platform/registry-mcp/`)

Entry point: `blue-data-registry-mcp`. Exposes DataRegistry operations to LLM clients.

**Explore tools:**

| Tool | Description |
|------|-------------|
| `search_records(query, record_type?, scope?, limit=10)` | Hybrid BM25 + vector search over all registry records |
| `list_sources()` | List all registered source names |
| `list_source_databases(source)` | List databases under a source |
| `list_database_collections(source, database)` | List collections within a database |
| `list_collection_entities(source, database, collection)` | List entities (tables) within a collection |

**Inspect tools:**

| Tool | Description |
|------|-------------|
| `get_entity(source, database, collection, entity)` | Full entity record with all attributes and enrichment properties |
| `get_record(name, record_type, scope)` | Specific record by (name, type, scope) identity |

**Manage tools:**

| Tool | Description |
|------|-------------|
| `sync_source(source, recursive=True)` | Walk live source and reconcile registry; idempotent |
| `collect_source_stats(source, recursive=True)` | Gather stats from live source into registry |
| `enrich_source(source)` | Deterministic semantic type inference on all attributes |
| `enrich_source_metadata(source, recursive=True, rebuild=False)` | Full MetaData enrichment pipeline |

**Query tools:**

| Tool | Description |
|------|-------------|
| `execute_query(source, query, database?, collection?)` | Execute native SQL and return rows as JSON array |
| `import_data(source, target, collection?, database?, entity?, mode="append")` | Copy rows between registered sources |

All tools return a JSON-encoded string.

---

### JSON MCP (`platform/json-mcp/`)

Entry point: `blue-data-json-mcp`. Provides raw key-value access to the JSONSource backing store — useful for debugging registry state without going through the DataRegistry abstraction.

| Tool | Description |
|------|-------------|
| `json_get(path)` | Read value at a registry path; `"$"` reads the root |
| `json_set(path, value)` | Write value at a path |
| `json_delete(path)` | Delete value at a path |
| `json_list_keys(prefix?)` | List all known keys, optionally filtered by prefix |
| `json_get_all()` | Dump the entire backing store |

---

## 4. CLI

Package: `blue-data-cli`. Entry point: `blue-data`.

Global options: `--json` (raw JSON output), `--store` (override `BLUE_DATA_REGISTRY_STORE`), `--config` (override `BLUE_DATA_SOURCES_CONFIG`).

```
blue-data [--json] [--store memory|redis] [--config PATH] <command> [args]
```

### `source` group

```
blue-data source list
blue-data source add NAME --type sqlite|postgres [--database-dir DIR] [--host HOST] [--port N] [--dbname DB] [--user USER] [--password PW]
blue-data source remove NAME
blue-data source sync NAME [--no-recursive]
blue-data source stats NAME [--no-recursive]
blue-data source enrich NAME
blue-data source metadata NAME [--rebuild]
blue-data source query NAME SQL [--database DB]
blue-data source inspect NAME [DATABASE [COLLECTION [ENTITY [ATTRIBUTE]]]]
```

### Search

```
blue-data search QUERY [--type TYPE] [--limit N]
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLUE_DATA_REGISTRY_STORE` | `memory` | Registry backend: `memory`, `redis`, or `file` |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis URL; used when `STORE=redis` |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key prefix in Redis |
| `BLUE_DATA_REGISTRY_FILE` | `blue_data_store.json` | Path for file backend |
| `BLUE_DATA_REGISTRY_VECTOR_DIM` | `1536` | Embedding dimension for search index |
| `BLUE_DATA_LLM_PROVIDER` | — | `anthropic` or `openai`; omit for deterministic-only enrichment |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` (anthropic) / `gpt-4o` (openai) | LLM model for MetaData enrichment |
| `ANTHROPIC_API_KEY` | — | Required when `BLUE_DATA_LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | — | Required when `BLUE_DATA_LLM_PROVIDER=openai` |
| `BLUE_DATA_SOURCES_CONFIG` | — | Path to JSON file pre-loading data sources at startup |
| `BLUE_DATA_SOURCES_SYNC` | `true` | Auto-sync sources loaded from config file |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT` | — | Override BM25 weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT` | — | Override vector weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT` | — | Override value-match weight in hybrid search |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD` | — | Minimum BM25 score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD` | — | Minimum vector score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD` | — | Minimum combined score to include in results |
| `BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL` | — | `1`/`true` to enable hierarchical score boosting |
