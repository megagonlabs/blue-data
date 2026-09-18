# blue-data — Library

---

## DataRegistry(Registry)

Top-level entry point for all blue-data operations. Extends `Registry` with live-source management, enrichment, stats collection, and hybrid search. Owns a dict of named `DataSource` objects and coordinates writes to the `JSONSource`-backed catalog with indexing into `VectorSource` for search.

### Constructor

```python
DataRegistry(
    store: JSONSource | None = None,
    vector_source: VectorSource | None = None,
    metadata_enricher: MetaData | None = None,
    rebuild: bool | None = None,
)
```

- `store` — registry persistence backend; defaults to `MemoryJSONSource` if omitted
- `vector_source` — vector index backend; defaults to `MemoryVectorSource`
- `metadata_enricher` — `MetaData` instance for Layer 2 enrichment; `None` disables LLM-dependent enrichments
- `rebuild` — instance-level default for the `rebuild` flag passed to all write operations; `None` means each call decides

### Example

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry(
    metadata_enricher=MetaData(llm_fn=my_llm_fn)
)

source = SQLiteDBSource(
    name="northwind",
    properties={"connection": {"database_directory": "/data"}}
)
registry.register_source(source)
registry.sync_source("northwind", recursive=True)
registry.collect_source_stats("northwind", recursive=True)
registry.enrich_source_metadata("northwind", recursive=True)

results = registry.search_records("shipping cost")
```

### Source management

| Method | Description |
|--------|-------------|
| `register_source(source)` | Add a `DataSource` to `self.sources` and create its top-level registry record |
| `deregister_source(name)` | Remove a source and all its descendant records from the registry |
| `get_source(name)` | Return the live `DataSource` object for `name` |

### Sync

| Method | Description |
|--------|-------------|
| `sync_source(name, recursive=False)` | Walk the live source and reconcile its structure into the registry; with `recursive=True` descends databases → collections → entities/attributes/relations in one call |
| `sync_source_database(name, database)` | Sync a single database |
| `sync_source_database_collection(name, database, collection)` | Sync a single collection; computes adds/removes/merges vs the current registry and updates records accordingly |

Sync is **idempotent** — running it twice on an unchanged source produces no diff.

### Stats

| Method | Description |
|--------|-------------|
| `collect_source_stats(name, recursive=False)` | Fetch stats from the live source and write them as `record["properties"]["stats"]`; `recursive=True` descends the full hierarchy |
| `collect_source_database_stats(name, database)` | Stats for a single database (`size_bytes`, `table_count`) |
| `collect_source_database_collection_stats(...)` | Stats for a single collection (`num_entities`, `num_relations`) |
| `collect_source_database_collection_entity_stats(...)` | Stats for a single entity (`row_count`) |
| `collect_source_database_collection_entity_attribute_stats(...)` | Stats for a single attribute (`count`, `distinct_count`, `null_count`, `sample_values`, `min`, `max`) |

Stats must be collected before enrichment — `sample_values` is the primary input to `SemanticTypeInferencer`.

### Enrichment

| Method | Description |
|--------|-------------|
| `enrich_source(name)` | Layer 1 only — runs `SemanticTypeInferencer` on every attribute's sample values; no LLM required |
| `enrich_source_metadata(name, recursive=False, rebuild=False)` | Layer 1 + Layer 2 — calls `enrich_source` first, then delegates to `MetaData.collect_source_metadata`; LLM enrichments are skipped if no `metadata_enricher` was set |

**Required order:**

```
sync_source(recursive=True)             # 1
collect_source_stats(recursive=True)    # 2
enrich_source_metadata(recursive=True)  # 3
```

### Search

| Method | Description |
|--------|-------------|
| `search_records(query, source=None, type=None, k=10, ...)` | Hybrid BM25 + vector search over all registry records; optionally scoped to a source name or record type |

---

## Registry

Key/value catalog that persists records under path keys of the form `{scope}/{type}/{name}`. Backed by a `JSONSource`. Fires `_on_record_changed` / `_on_record_deleted` hooks that trigger vector indexing when `rebuild=True`.

### Record path convention

```
/{scope}/{type}/{name}
```

| Level | type | Example path |
|-------|------|-------------|
| Source | `source` | `/source/sqlite` |
| Database | `database` | `/source/sqlite/database/mydb` |
| Collection | `collection` | `/source/sqlite/database/mydb/collection/public` |
| Entity | `entity` | `/source/sqlite/database/mydb/collection/public/entity/users` |
| Attribute | `attribute` | `/source/sqlite/database/mydb/collection/public/entity/users/attribute/id` |
| Relation | `relation` | `/source/sqlite/database/mydb/collection/public/relation/users_orders` |

### Record schema

Every record is a dict with these standard fields:

```python
{
    "name": "users",
    "type": "entity",
    "scope": "/source/sqlite/database/mydb/collection/public",
    "description": "",
    "created_by": None,
    "icon": None,
    "properties": {},   # arbitrary key/value metadata (stats, semantics, descriptions)
    "contents": {},     # unused in records; populated during schema export
}
```

### Methods

| Method | Description |
|--------|-------------|
| `register_record(path, record, rebuild=None)` | Create or overwrite a record; triggers indexing when `rebuild=True` |
| `update_record(path, updates, rebuild=None)` | Merge `updates` into the existing record at `path` |
| `get_record(path)` | Return the record at `path`; `None` if not found |
| `delete_record(path, rebuild=None)` | Remove the record and its descendants; triggers index deletion |
| `list_records(prefix=None)` | Return all records, optionally filtered by path prefix |
| `load(data)` / `loads(json_str)` | Bulk-load a dict or JSON string into the registry; rebuilds the full vector index after |
| `dump()` / `dumps()` | Serialize the registry to a dict or JSON string |

### `rebuild` flag

Three-state flag on all write methods:

| Value | Behaviour |
|-------|-----------|
| `True` | Force vector index update for this write |
| `False` | Suppress vector index update for this write |
| `None` | Defer to `DataRegistry._rebuild` instance default |

---

## DataSource

Abstract base class for all external data adapters. Each implementation exposes a consistent interface for listing and querying databases, collections, entities, attributes, and relations. Subclasses override only the methods they support; unsupported methods raise `NotImplementedError`.

### Key methods

| Method | Description |
|--------|-------------|
| `fetch_databases()` | List available databases |
| `fetch_database_collections(database)` | List collections (schemas/tables) within a database |
| `fetch_database_collection_entities(database, collection)` | List entities (tables/document types) within a collection |
| `fetch_database_collection_entity_attributes(database, collection, entity)` | List attributes (columns/fields) of an entity |
| `fetch_database_collection_relations(database, collection)` | List foreign-key or reference relations |
| `execute_query(database, query, optional_properties=None)` | Execute an ad-hoc query against the live source |
| `fetch_*_stats(...)` | Collect stats at each level of the hierarchy |

### Implementations

| Class | Backend | Status |
|-------|---------|--------|
| `SQLiteDBSource` | SQLite `.db` files | Full |
| `PostgresDBSource` | PostgreSQL | Full |
| `MongoDBSource` | MongoDB | Full |
| `NEO4JSource` | Neo4j property graph | Full |
| `MySQLDBSource` | MySQL | Full |
| `FileSource` | CSV / JSON / JSONL files | Full |
| `RedisSource` | Redis key-value | **Not yet implemented** |

---

## JSONSource

Abstract base class for the registry's persistence backend. Exposes a minimal get/set/delete interface over a flat key-value store keyed by registry paths.

### Methods

| Method | Description |
|--------|-------------|
| `get(path)` | Return the value at `path`; `None` if absent |
| `set(path, value)` | Write `value` at `path` |
| `delete(path)` | Remove `path` and all keys with that prefix |
| `list_keys(prefix=None)` | Return all keys, optionally filtered by prefix |

### Implementations

| Class | Storage | Use |
|-------|---------|-----|
| `MemoryJSONSource` | Python `dict` in process | Development, testing |
| `FileJSONSource` | Atomic JSON file on disk | Lightweight persistence; no server |
| `MongoDBSource` | MongoDB | Production alternative to Redis |
| `RedisJSONSource` | Redis Stack (`JSON.SET` / `JSON.GET`) | Production; requires `redis-stack-server` |

`RedisJSONSource` stores each registry path as a separate Redis key prefixed by a configurable namespace. `list_keys` performs a SCAN. All operations are synchronous.

---

## VectorSource

Pluggable vector index used by the search engine. Completely separate from `DataSource` and `JSONSource`. All operations are dispatched through a single `execute_query(op, ...)` interface.

### Operations

| Op | Description |
|----|-------------|
| `VECTOR.CREATE_INDEX` | Create a vector index for a named collection with a given dimensionality |
| `VECTOR.UPSERT` | Insert or overwrite a vector record by ID |
| `VECTOR.DELETE` | Remove a vector record by ID |
| `VECTOR.KNN` | Find the K nearest neighbours to a query vector |

### Implementations

| Class | Storage | Use |
|-------|---------|-----|
| `MemoryVectorSource` | Python `dict` + numpy cosine distance | Development, testing |
| `FileVectorSource` | File-persisted vectors | Lightweight persistence; no server |
| `ChromaDBVectorSource` | ChromaDB | Production alternative to Redis |
| `RedisVectorSource` | RedisJSON + RediSearch KNN (`FT.CREATE` / `FT.SEARCH`) | Production; requires `redis-stack-server` |

---

## MetaData

Orchestrates both layers of semantic enrichment. Accepts an optional `llm_fn` callable — `(prompt: str) -> str` — which is called for LLM-dependent enrichments. Without it, Layer 1 runs and Layer 2 LLM steps silently return `None`.

### Constructor

```python
MetaData(llm_fn: Callable[[str], str] | None = None)
```

### Enrichment layers

**Layer 1 — Deterministic** (`enrich_source`):

Runs `SemanticTypeInferencer` on `attribute.properties["stats"]["sample_values"]`. No LLM required. Detected properties:

| Property | Location | Description |
|----------|----------|-------------|
| `value_semantics.semantic_type` | `attribute` | `ENUM`, `BINARY_FLAG`, `NUMERIC_ID`, `CONTINUOUS`, etc. |
| `process_semantics` | `entity` | `EVENT_LOG`, `SNAPSHOT`, `REFERENCE` |
| `semantic_links` | `entity` | Foreign-key and natural join candidates |
| `value_axis` | `entity` | Whether the entity has a natural value axis (event time) |

**Layer 2 — LLM-augmented** (`collect_source_metadata`, calls `enrich_source` first):

| Property | Location | Requires LLM |
|----------|----------|-------------|
| `semantic_role` | `attribute` | No |
| `quantitative_vst` | `attribute` | No |
| `value_semantics` (richer) | `attribute` | Yes (`enrich_attribute_vsi`) |
| `semantic_discovery` | `attribute` | Yes (`infer_attribute_sdi`) |
| `description` | `entity` | Yes (`enrich_entity`) |

### `llm_fn` contract

Any callable `(str) -> str`. The simplest wiring:

```python
import anthropic
client = anthropic.Anthropic()

def llm_fn(prompt: str) -> str:
    return client.messages.create(
        model="claude-opus-4-8", max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    ).content[0].text

enricher = MetaData(llm_fn=llm_fn)
```

---

## RegistrySearch

Wires the hybrid search engine into the registry. Owned by `DataRegistry`. Holds a `HybridSearch` instance (BM25 + vector scoring) and a `RecordIndexer` that keeps `VectorSource` in sync with every registry write.

### Classes

| Class | Role |
|-------|------|
| `RegistrySearch` | Top-level: holds `HybridSearch` + `RecordIndexer`; called by `DataRegistry.search_records` |
| `HybridSearch` | Orchestrates BM25 + vector scoring, applies thresholds, returns ranked results |
| `VectorSearch` | Embeds query text and calls `VECTOR.KNN` against `VectorSource` |
| `RecordIndexer` | Upserts and deletes records in `VectorSource` on every registry write |
| `KeywordSearch` | BM25-only fallback when no `VectorSource` is configured |

### Search pipeline

```
search_records(query)
  └─ RegistrySearch.hybrid_search(query)
       ├─ BM25 pass:    score each record's name + description text
       ├─ Vector pass:  embed query → VECTOR.KNN → cosine similarity scores
       ├─ combine_scores(bm25_weight, vector_weight, value_weight)
       ├─ apply thresholds (bm25_threshold, vector_threshold, combined_threshold)
       └─ return top-k ranked records
```

Weights do not need to sum to 1 — they are normalized automatically. Defaults:

| Weight / threshold | Default |
|--------------------|---------|
| `bm25_weight` | `0.3` |
| `vector_weight` | `0.7` |
| `value_weight` | `0.15` |
| `bm25_threshold` | `0.0` |
| `vector_threshold` | `0.5` |
| `combined_threshold` | `0.36` |

All defaults are overridable via environment variables (see `BLUE_DATA_REGISTRY_SEARCH_*` in `README.md`).

### Index lifecycle

Records are indexed into `VectorSource` on every `register_record` / `update_record` call when `rebuild=True`. The full index is rebuilt in bulk after `Registry.load()` / `Registry.loads()`. `RecordIndexer` handles both upserts and deletions — removing a record from the registry removes it from the vector index in the same call.
