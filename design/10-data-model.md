# blue-data — Data Model

## Overview

`blue-data` is built around three independent data hierarchies that compose in `DataRegistry`. Understanding which hierarchy owns what is the key to reading the codebase.

| Hierarchy | Base class | What it represents |
|-----------|-----------|-------------------|
| External data | `DataSource` | SQL tables, graph nodes/edges, files, streams — the actual data being catalogued |
| Registry storage | `JSONSource` | Where registry records are persisted (in-memory dict, Redis, MongoDB, file) |
| Semantic search | `VectorSource` | Where embedded records are indexed for KNN search |

These three are explicitly separate. `JSONSource` and `VectorSource` extend `DataSource` only to inherit the lifecycle / property protocol — they are not "data sources" in the external-data sense.

---

## 1. DataSource

The base class for all external data adapters (`SQLiteDBSource`, `Neo4JGraphSource`, `BayesianNetworkSource`, etc.).

**Lifecycle:**

```python
DataSource(name, properties)   # __init__ → _initialize → _start → _connect
DataSource._stop()             # _stop → _disconnect (explicit teardown)
```

**Interface methods (all return sensible defaults — no exceptions for unsupported ops):**

| Method group | Methods |
|-------------|---------|
| Source-level | `fetch_metadata()`, `fetch_schema()` |
| Database-level | `fetch_databases()`, `fetch_database_metadata(db)`, `create_database(db)` |
| Collection-level | `fetch_database_collections(db)`, `fetch_database_collection_metadata(db, coll)`, `fetch_database_collection_entities(db, coll)`, `fetch_database_collection_relations(db, coll)`, `create_database_collection(db, coll)` |
| Entity/relation | `create_database_collection_entity(...)`, `create_database_collection_relation(...)` |
| Query | `execute_query(query, database, collection, optional_properties)` |
| NL query | `execute_query_nl(...)`, `execute_query_nl_tools(...)` |
| Import | `import_data(source, database, collection, entity, mode, options)` |
| Stats | `fetch_source_stats()`, `fetch_database_stats(db)`, `fetch_collection_stats(...)`, `fetch_entity_stats(...)`, `fetch_property_stats(...)` |
| Transactions | `begin_transaction(db)`, `commit_transaction(tid)`, `rollback_transaction(tid)` |

**NL tool loop:**

`execute_query_nl_tools` drives a multi-turn Claude tool loop. It calls `get_nl_tools()` to get Anthropic-format tool definitions (list_databases, list_collections, get_schema, get_metadata, execute_query, get_sample, get_column_stats, get_relations), then iterates until the model calls `end_turn` or `max_iterations` is reached. `VectorSource` overrides `get_nl_tools` with vector-specific tools (list_indexes, search_similar, etc.).

**Instantiation by class path:**

```python
DataSource.instantiate(
    "blue_data.source.sql.sqlite.sqlite_sql_source.SQLiteDBSource",
    "my_source",
    properties={"dir": "/data/dbs"},
)
```

---

## 2. DataSchema

An in-memory entity/relation graph built by `DataSource` subclasses during `fetch_database_collection_entities`. Returned as a dict from `get_entities()` / `get_relations()`.

### Entity object

```python
{
    "name":        str,          # entity name (e.g. "Orders")
    "index":       int,          # 0-based deduplication suffix counter
    "description": str,          # human-readable description; "" if not set
    "created_by":  str | None,   # creator tag (e.g. "llm", "sync")
    "properties":  {},           # future type-level metadata; usually empty
    "contents": {
        "attributes": {
            "column_name": {
                "name":        str,
                "info":        str,  # SQL type string (e.g. "INTEGER", "TEXT")
                "description": str,
            }
        }
    },
    "icon": str | None,
}
```

### Relation object

```python
{
    "name":        str,      # relation type (e.g. "FOREIGN_KEY")
    "index":       int,
    "source":      str,      # source entity name
    "target":      str,      # target entity name
    "description": str,
    "properties":  {},       # relation-level metadata
    "contents": {
        "attributes": { ... }  # same structure as entity attributes
    },
}
```

### Deduplication

When two entities share the same name, the second gets a `__1` suffix as its dict key (e.g., `"Orders"` → key `"Orders"`, `"Orders"` again → key `"Orders__1"`). The `name` field stays `"Orders"` for both; the key encodes uniqueness.

### Key methods

| Method | Returns |
|--------|---------|
| `add_entity(key, description, index)` | `str` (the key) |
| `add_entity_attribute(key, attribute, type, description)` | None |
| `add_relation(source, relation, target, description, index)` | `str` (unique key) |
| `add_relation_attribute(key, attribute, type, description)` | None |
| `get_entities()` | `dict[str, entity_obj]` |
| `get_relations()` | `dict[str, relation_obj]` |
| `to_json()` | `{"entities": {...}, "relations": {...}}` |
| `DataSchema.from_json(data)` | `DataSchema` |
| `to_str(simplified=True)` | Compact human-readable string for LLM prompts |

---

## 3. JSONSource

The persistence interface for `Registry`. All registry records are stored as JSON values addressed by string paths.

```python
class JSONSource(DataSource, ABC):
    def get(self, path: str | None = None) -> Any: ...
    def set(self, path: str | None, value: Any) -> None: ...
    def delete(self, path: str | None = None) -> None: ...
```

`execute_query` dispatches on `op`:

| `op` | Effect |
|------|--------|
| `GET` / `JSON.GET` | `get(path)` |
| `SET` / `JSON.SET` | `set(path, value)` |
| `DEL` / `DELETE` / `JSON.DEL` | `delete(path)` |

### Backends

| Class | Persistence | Notes |
|-------|-------------|-------|
| `MemoryJSONSource` | None (in-process dict) | Default; used in tests and dev |
| `FileJSONSource` | File (atomic write) | Uses JSONPath for nested gets/sets |
| `RedisJSONSource` | Redis Stack | Each registry path becomes a Redis key prefixed by namespace |
| `MongoDBJSONSource` | MongoDB | — |

---

## 4. VectorSource

The search index interface. Stores document embeddings and supports KNN retrieval.

```python
class VectorSource(DataSource, ABC):
    def create_index(self, index_name, collection, dim, distance_metric="COSINE", extra_fields=None) -> str: ...
    def upsert(self, collection, doc_id, doc, embedding_field="embedding") -> str: ...
    def delete(self, collection, doc_id) -> int: ...
    def knn(self, index_name, query_vector, k=5, embedding_field="embedding",
            score_alias="score", return_fields=None, filter_expr="*") -> list[dict]: ...
```

`execute_query` dispatches on `op`:

| `op` | Required fields | Purpose |
|------|----------------|---------|
| `VECTOR.CREATE_INDEX` | `index`, `collection`, `dim` | Create a new vector index |
| `VECTOR.UPSERT` | `collection`, `id`, `doc` | Add or update a document |
| `VECTOR.DELETE` | `collection`, `id` | Remove a document |
| `VECTOR.KNN` | `index`, `vector`/`embedding` | Find k nearest neighbours |

`VECTOR.KNN` accepts `vector`, `embedding`, `query_vector`, or `query_embedding` interchangeably as the query vector key.

### Backends

| Class | Persistence | Notes |
|-------|-------------|-------|
| `MemoryVectorSource` | None (in-process) | numpy cosine; used in tests and dev |
| `FileVectorSource` | File | Numpy-backed persistence |
| `RedisVectorSource` | Redis Stack | RediSearch `FT.SEARCH … KNN`; production backend |
| `ChromaDBVectorSource` | ChromaDB | — |

---

## 5. Registry Record

The core data structure persisted by `Registry` via `register_record(...)`.

```python
record = {
    "name":        str,          # record identifier within its scope+type
    "type":        str,          # record type string: "source", "database", "collection", "entity", "relation", "attribute"
    "scope":       str,          # parent path: "/" for top-level, "/source/mydb/database/main" for deeper
    "description": str,          # human-readable description
    "created_by":  str | None,   # "sync", "llm", or None
    "properties":  dict,         # arbitrary key/value; includes "stats", "metadata", enrichment props
    "icon":        str | None,   # optional display icon
    "contents":    dict,         # nested child records (filled by DataRegistry typed helpers)
}
```

**Storage key:** `{scope}/{type}/{name}` — e.g., `/source/northwind/database/main/collection/public/entity/Orders`. The root sentinel key `$` holds top-level store metadata.

**Typed path convention:**

```
/                                  → root ($)
/{type}/{name}                     → source-level record  (type="source")
/source/{s}/database/{db}          → database record
/source/{s}/database/{db}/collection/{c}  → collection record
/source/{s}/database/{db}/collection/{c}/entity/{e}     → entity record
/source/{s}/database/{db}/collection/{c}/entity/{e}/attribute/{a}  → attribute record
/source/{s}/database/{db}/collection/{c}/relation/{r}   → relation record
```

---

## 6. Enrichment Properties

`MetadataEnricher` stores its results as sub-keys inside `record["properties"]`. These are written back to the Registry store after enrichment runs.

**On attribute records:**

| Property key | What it stores |
|-------------|----------------|
| `value_semantics` | VSI: rich semantic type + flags (e.g. CATEGORICAL, BINARY, RATE) |
| `semantic_discovery` | SDI: open-world concept discovery |
| `domain_concept` | DCM: taxonomy mapping |
| `interpretive_sem` | IVS: ordinal/severity/tier ordering |
| `value_axis` | Magnitude or ordinal axis classification |
| `quantitative_vst` | MEASUREMENT / COUNT / PROPORTION / RATE |
| `safe_aggregation` | `{can_sum, can_avg, forbidden_combinations}` |
| `semantic_role` | IDENTIFIER / EVENT_TIME / SEGMENTATION_DRIVER / MEASURE |
| `role_query_constraints` | Per-attribute query-planning flags (can_group_by, should_not_sum, …) |
| `process_vst_role` | PROCESS_KEY / EVENT_TIME / EVENT_MEASURE / STATE_VAR |
| `time_grain_candidates` | Inferred time bucketing granularities |

**On entity records:**

| Property key | What it stores |
|-------------|----------------|
| `semantic_links` | Validated inter-attribute relationships |
| `total_component_measures` | TOTAL/COMPONENT numeric relationships (prevents double-counting) |
| `derived_metric_candidates` | Rate/ratio candidates for NL2SQL (e.g. `injuries_per_event`) |
| `process_semantics` | EVENT row semantics |
| `process_patterns` | Temporal cadence |
| `process_trends` | Trend direction per measure |
| `process_operators` | NL2SQL operators (AGGREGATE_OVER_TIME, CHANGE_DETECTION, …) |
| `process_query_constraints` | Query planner constraints derived from process operators |
| `conditional_value_distribution` | P(value \| group) |

**Deterministic enrichment** (runs without `llm_fn`): `SemanticTypeInferencer` — column type inference from SQL type strings (INTEGER → NUMERIC, VARCHAR → CATEGORICAL, etc.).

**LLM-backed enrichment** (requires `llm_fn`): All properties above; prompted via `registry/enrichment/prompts.py`.

---

## 7. DataRegistry

`DataRegistry` extends `Registry` and wires all three hierarchies together.

```python
DataRegistry(
    name="DATA_REGISTRY",
    store=None,            # JSONSource; defaults to MemoryJSONSource
    vector_source=None,    # VectorSource; search disabled if None
    embedding_fn=None,     # callable(str) → list[float]
    rebuild=False,         # whether to index records on every write
    index_name="registry_index",
    vector_dim=1536,
    hybrid_config=None,    # BM25/vector weight config
    metadata_enricher=None,
)
```

Key additions over `Registry`:

| Method | Purpose |
|--------|---------|
| `register_source(source)` | Add a DataSource and its top-level registry record |
| `get_source(name)` | Return the live DataSource object |
| `sync_source(source, recursive=False)` | Walk the DataSource hierarchy and register all records |
| `collect_*_stats()` | Fetch live stats from the source and store them in `properties["stats"]` |
| `search_records(query, ...)` | Hybrid BM25 + vector search over all registry records |
| `enrich_collection(source, db, coll)` | Run MetadataEnricher and write enrichment props back |

**Rebuild hook:** Every `register_record` call fires `_on_record_changed`. When `rebuild=True` (or `rebuild` overrides the instance default), `RegistrySearch.index_record(record)` is called immediately to keep the vector index in sync.
