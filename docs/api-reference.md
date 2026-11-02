# API Reference

> **Platform docs:** For the MCP server tool reference and configuration, see [`registry-mcp.md`](registry-mcp.md).

---

## `DataSource`

Base class for all data source adapters. Subclasses override only the methods they support; the defaults return empty results without raising.

```python
from blue_data.source.source import DataSource

DataSource(name: str, properties: dict | None = None)
```

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Unique name used as the registry source key |
| `properties` | `dict` | Source-level configuration (connection params, etc.) |

**Source-level methods**

| Method | Returns | Description |
|---|---|---|
| `fetch_metadata()` | `dict` | Arbitrary metadata for the source |
| `fetch_schema()` | `dict` | Top-level schema info |
| `fetch_source_stats()` | `dict \| None` | Source-level statistics |

**Database-level methods**

| Method | Returns | Description |
|---|---|---|
| `fetch_databases()` | `list[str]` | Names of all databases |
| `fetch_database_metadata(database)` | `dict` | Metadata for a database |
| `fetch_database_schema(database)` | `dict` | Schema info for a database |
| `fetch_database_stats(database)` | `dict \| None` | Statistics for a database |
| `create_database(database, properties)` | `dict` | Create a new database |

**Collection-level methods**

| Method | Returns | Description |
|---|---|---|
| `fetch_database_collections(database)` | `list[str]` | Collections (schemas/namespaces) in a database |
| `fetch_database_collection_metadata(database, collection)` | `dict` | Collection metadata |
| `fetch_database_collection_entities(database, collection)` | `dict` | Entity map (see below) |
| `fetch_database_collection_relations(database, collection)` | `dict` | Relation map |
| `fetch_collection_stats(database, collection, entities, relations, sample_limit)` | `dict \| None` | Collection-level statistics |
| `create_database_collection(database, collection, properties)` | `dict` | Create a new collection |

**Entity / relation methods**

| Method | Returns | Description |
|---|---|---|
| `create_database_collection_entity(database, collection, entity, properties)` | `dict` | Create a table or entity |
| `create_database_collection_relation(database, collection, relation, properties)` | `dict` | Create a relation |
| `fetch_entity_stats(database, collection, entity)` | `dict \| None` | Row-level stats for an entity |
| `fetch_property_stats(database, collection, entity, property_name, sample_limit)` | `dict \| None` | Column-level stats |

**Query**

| Method | Returns | Description |
|---|---|---|
| `execute_query(query, database, collection, optional_properties)` | `list[dict]` | Run an ad-hoc query and return rows as dicts |
| `execute_query_nl(query, database, collection, schema, llm_fn, optional_properties)` | `list[dict]` | Translate NL query to native and execute (one-shot) |
| `execute_query_nl_tools(query, database, collection, llm_fn, optional_properties, max_iterations, extra_tools, extra_tool_fn)` | `list[dict]` | Drive a multi-turn LLM tool loop to answer a NL query |
| `get_nl_tools(database, collection)` | `list[dict]` | Return Anthropic-format tool definitions for the tool loop; override per dialect |
| `execute_nl_tool(name, tool_input, database, collection, optional_properties)` | `Any` | Dispatch a single named tool call; override per dialect |

**Entity dict format** returned by `fetch_database_collection_entities`:

```python
{
  "users": {
    "name": "users",
    "properties": {},
    "contents": {
      "attributes": {
        "id":   {"name": "id",   "info": {"type": "INTEGER"}, "description": None},
        "name": {"name": "name", "info": {"type": "TEXT"},    "description": None},
      }
    }
  }
}
```

---

## `Registry`

Generic key/value catalog backed by a `JSONSource`. All records are addressable by `(name, type, scope)`.

```python
from blue_data.registry.registry import Registry

Registry(name: str = "REGISTRY", store: JSONSource | None = None)
```

**Record CRUD**

| Method | Returns | Description |
|---|---|---|
| `register_record(name, type, scope, description, properties, created_by, icon, rebuild)` | `dict` | Create and store a new record |
| `get_record(name, type, scope)` | `dict \| None` | Retrieve a record by identity |
| `update_record(name, type, scope, description, properties, icon, rebuild)` | `tuple \| dict` | Upsert a record, deep-merging properties |
| `deregister_record(name, type, scope, rebuild)` | `None` | Delete a record |
| `deregister(record, rebuild)` | `None` | Delete using a record dict |
| `list_records(record_type, scope, recursive)` | `list[dict]` | Query records by type/scope |
| `filter_record_contents(name, type, scope, filter_type, filter_name, single)` | `list[dict]` | Find child records under a parent path |

The `rebuild` parameter on write methods controls search index updates: `True` forces re-indexing, `False` suppresses it, `None` defers to the instance-level default (`DataRegistry._rebuild`).

**Properties**

| Method | Returns | Description |
|---|---|---|
| `get_record_properties(name, type, scope)` | `dict` | All properties on a record |
| `get_record_property(name, type, scope, key)` | `Any` | Single property value |
| `set_record_property(name, type, scope, key, value, rebuild)` | `dict` | Set a property |
| `delete_record_property(name, type, scope, key, rebuild)` | `Any` | Remove a property, returns old value |
| `get_record_description(name, type, scope)` | `str \| None` | Description field |
| `set_record_description(name, type, scope, description, rebuild)` | `dict` | Set description field |

**Data access**

| Method | Returns | Description |
|---|---|---|
| `get_record_data(name, type, scope, key)` | `Any` | Return full record or a specific top-level key |
| `set_record_data(name, type, scope, key, value, rebuild)` | `dict` | Set an arbitrary top-level key on a record |
| `delete_record_data(name, type, scope, key, rebuild)` | `dict` | Delete an arbitrary top-level key |

**Filtering**

| Method | Returns | Description |
|---|---|---|
| `filter_records_by_properties(record_type, scope, properties, recursive, partial_match)` | `list[dict]` | Filter records whose `properties` match a nested dict. `partial_match=True` does substring matching on values |

**Serialization**

| Method | Description |
|---|---|
| `dumps()` | JSON string of all records |
| `dump(output_file)` | Write all records to a file |
| `loads(input_string)` | Load records from a JSON string |
| `load(input_file)` | Load records from a file |
| `register_record_json(record, recursive, rebuild)` | Register a record dict (and optionally its nested `contents`) |
| `build_index()` | Bulk re-index all records into the search index |

---

## `DataRegistry`

Extends `Registry` with live-source operations and hybrid search. The central class for most use.

```python
from blue_data.registry.data_registry import DataRegistry

DataRegistry(
    name: str = "DATA_REGISTRY",
    store: JSONSource | None = None,
    vector_source: VectorSource | None = None,
    embedding_fn: Callable[[str], list[float]] | None = None,
    rebuild: bool = False,
    index_name: str = "registry_index",
    vector_dim: int = 1536,
    hybrid_config: dict | None = None,
    metadata_enricher: MetaData | None = None,
)
```

| Parameter | Description |
|---|---|
| `store` | Registry storage backend. Defaults to `MemoryJSONSource` |
| `vector_source` | Vector index for search. Omit to use keyword-only search |
| `embedding_fn` | Callable that converts text to a vector of length `vector_dim` |
| `rebuild` | If `True`, index every record on write. If `False`, only index on explicit `build_index()` |
| `index_name` | Name of the vector index created in `VectorSource` |
| `vector_dim` | Dimensionality of embedding vectors |
| `hybrid_config` | Override any key from `DEFAULT_PARAMS` (see Search section below) |
| `metadata_enricher` | `MetaData` instance to use for `enrich_source_metadata`. Pass `MetaData(llm_fn=None)` for deterministic-only enrichment or `MetaData(llm_fn=fn)` for LLM-augmented enrichment |

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `sources` | `dict[str, DataSource]` | Live source objects by name |
| `search_engine` | `RegistrySearch` | Hybrid search engine |

### Source management

| Method | Description |
|---|---|
| `register_source(source)` | Register a `DataSource` and write its top-level record |
| `get_source(name)` | Return the live `DataSource` for `name` |
| `list_sources()` | Names of all registered sources |
| `deregister_source(source)` | Remove source object and its registry record |
| `execute_query(source, query, database, collection, optional_properties)` | Delegate query to the named source |

### Hierarchy helpers

Typed wrappers around `register_record` / `get_record` / `list_records` / `update_record` / `deregister_record`. Pattern: `{verb}_source_database[_collection[_entity[_attribute]]]`.

**Register**
```python
register_source_database(source, database, description, properties)
register_source_database_collection(source, database, collection, ...)
register_source_database_collection_entity(source, database, collection, entity, ...)
register_source_database_collection_entity_attribute(source, database, collection, entity, attribute, ...)
register_source_database_collection_relation(source, database, collection, relation, ...)
register_source_database_collection_relation_attribute(source, database, collection, relation, attribute, ...)
```

**Get / List / Update / Deregister** — same naming pattern.

### Sync

Reconcile registry records against the live source. Computes adds/removes/merges at each level.

| Method | Description |
|---|---|
| `sync_source(source, recursive=False)` | Walk source databases; with `recursive=True` descend to collections/entities/attributes |
| `sync_source_database(source, database, source_obj, recursive)` | Sync one database |
| `sync_source_database_collection(source, database, collection, source_obj)` | Sync entities, attributes, and relations for one collection |
| `sync_all(recursive=False)` | Sync all registered sources |

Sync is **idempotent**. After each collection sync, the collection's `schema` property is updated with a JSON snapshot of entities and relations.

### Stats collection

| Method | Persists to |
|---|---|
| `collect_source_stats(source, recursive=False)` | Source record + optionally all descendants |
| `collect_source_database_stats(source, database)` | Database record |
| `collect_source_database_collection_stats(source, database, collection)` | Collection record |
| `collect_source_database_collection_entity_stats(source, database, collection, entity)` | Entity record |
| `collect_source_database_collection_entity_attribute_stats(source, database, collection, entity, attribute)` | Attribute record |

### Semantic enrichment

| Method | Description |
|---|---|
| `enrich_source_database_collection_entity_attribute(source, db, col, entity, attr)` | Infer semantic type from `stats.sample_values` and write to `"value_semantics"` property |
| `enrich_source(source)` | Run `SemanticTypeInferencer` on all attributes across all collections (deterministic, no LLM) |
| `enrich_source_metadata(source, recursive=True, rebuild=False)` | Run the full `MetaData` pipeline — calls `enrich_source` first, then delegates to `self.metadata_enricher` if one was set at construction. With `rebuild=False`, existing enrichment properties are preserved (idempotent). |

`enrich_source_metadata` requires `metadata_enricher` to be set at `DataRegistry` construction. The prerequisite order must be followed:

```python
registry.sync_all(recursive=True)            # 1. discover schema
registry.collect_source_stats(recursive=True) # 2. gather sample_values
registry.enrich_source_metadata(...)         # 3. enrich
```

### Data quality profiling

| Method | Description |
|---|---|
| `compute_attribute_data_quality(source, database, collection, entity, attribute)` | Reads `stats` + `value_semantics` for one attribute, computes all DQ tiers, writes the result as the `"data_quality"` property |
| `compute_entity_data_quality_summary(source, database, collection, entity)` | Aggregates per-attribute `"data_quality"` dicts, computes entity-level metrics, writes `"data_quality_summary"`; also writes `misplaced_value_rate` back to each attribute's `"data_quality"` property |
| `compute_source_data_quality(source, recursive=True)` | Walks the full hierarchy, calling the attribute and entity methods in order |

Prerequisite order:

```python
registry.collect_source_stats("mydb", recursive=True)  # must run first
registry.enrich_source("mydb")                         # optional; sharpens Tier 2 format checks
registry.compute_source_data_quality("mydb")           # writes data_quality + data_quality_summary
```

**Per-attribute `"data_quality"` keys:**

| Tier | Keys |
|------|------|
| 1 | `missing_value_rate`, `fill_rate`, `is_partial_attribute`, `cardinality_ratio` |
| 2 | `disguised_missing_rate`, `format_violation_rate`, `heterogeneous_format_rate`, `embedded_value_rate` |
| 3 | `rare_value_rate`, `suspected_typo_rate`, `representation_fragmentation_rate`, `outlier_rate` |
| 4 | `repairability` (`deterministic`, `ambiguous`, `unrecoverable`), `misplaced_value_rate` |

**Per-entity `"data_quality_summary"` keys:** `effective_noise_rate`, `worst_attribute`, `dominant_error_type`, `columns_with_errors`, `columns_with_error_rate`, `duplicate_row_rate`, `rows_with_error_rate`, `multi_error_row_rate`, `misplaced_value_rate` (per-attribute map).

---

### connect_source

```python
registry.connect_source(source_name: str) -> DataSource | None
```

Lazily instantiate a `DataSource` from its stored registry record. Reads `properties.connection.protocol` to pick the right class, creates the live object, adds it to `registry.sources`, and returns it. Returns the already-registered live object if one exists. Returns `None` if the record has no connection properties.

Supported protocols: `sqlite`, `postgres`, `mysql`, `mongodb`, `bolt` / `neo4j`, `bn`.

```python
# Restore a source from a previously serialised registry
registry.loads(serialized_string)
source = registry.connect_source("my_sqlite")
dbs = source.fetch_databases()
```

---

### Create operations

| Method | Description |
|---|---|
| `create_source_database(source, database, properties, overwrite, recursive)` | Create database and sync |
| `create_source_database_collection(source, database, collection, properties, overwrite, recursive)` | Create collection and sync |
| `create_source_database_collection_entity(source, database, collection, entity, properties, creation_properties, overwrite, recursive)` | Create entity, auto-register missing parents, sync |
| `create_source_database_collection_relation(source, database, collection, relation, properties, overwrite, recursive)` | Create relation and sync |

### Search

```python
registry.search_records(
    input_query: str,
    type: str | None = None,
    scope: str | None = None,
    page: int = 0,
    page_size: int = 5,
    # score weights
    bm25_weight: float | None = None,      # default 0.3
    vector_weight: float | None = None,    # default 0.7
    value_weight: float | None = None,     # default 0.15
    # thresholds
    bm25_threshold: float | None = None,   # default 0.0
    vector_threshold: float | None = None, # default 0.5
    combined_threshold: float | None = None, # default 0.36
    # options
    bm25_normalization: str | None = None, # "minmax" | "softmax"
    enable_schema: bool | None = None,
    hierarchical_enabled: bool | None = None,
)
```

Returns `list[dict]` — records augmented with a `_score` field. When `type` is `"database"` or `"collection"` and `hierarchical_enabled=True`, automatically routes to `search_records_hierarchical` which propagates child relevance scores up to parent nodes.

**Default search parameters** (override via `hybrid_config` in constructor or per-call kwargs):

| Parameter | Default | Description |
|---|---|---|
| `bm25_weight` | `0.3` | Weight for BM25 keyword score |
| `vector_weight` | `0.7` | Weight for vector cosine similarity |
| `value_weight` | `0.15` | Weight for value-relevance score |
| `bm25_threshold` | `0.0` | Min BM25 score to include a record |
| `vector_threshold` | `0.5` | Min vector score to include a record |
| `combined_threshold` | `0.36` | Min combined score to return a record |
| `bm25_normalization` | `"minmax"` | BM25 normalisation method |
| `hierarchical_enabled` | `True` | Enable child → parent score propagation |

---

## `JSONSource`

Abstract base for the registry's storage backend.

```python
from blue_data.source.json.json_source import JSONSource

class JSONSource(ABC):
    def get(self, path: str) -> Any: ...
    def set(self, path: str, value: Any) -> None: ...
    def delete(self, path: str) -> None: ...
```

### `MemoryJSONSource`

In-memory implementation backed by a plain `dict`. Default when no store is passed to `Registry`.

```python
from blue_data.source.json.memory_json_source import MemoryJSONSource
```

### `RedisJSONSource`

Production backend. Stores each registry path as a separate Redis key prefixed by a configurable namespace.

```python
from blue_data.source.json.redis.redis_json_source import RedisJSONSource

# Connects from properties; the client is built from connection settings.
store = RedisJSONSource(properties={
    "namespace": "my_registry",
    "connection": {"host": "localhost", "port": 6379, "db": 0},
})
```

> Requires **Redis Stack** (`redis-stack-server`) for `JSON.SET` / `JSON.GET`.

---

## `VectorSource`

Base class for vector storage backends. Used by `RegistrySearch` to index and query record embeddings.

```python
from blue_data.source.vector.vector_source import VectorSource
```

All backends share the same `execute_query` interface with four operations:

```python
# Create index
source.execute_query({
    "op": "VECTOR.CREATE_INDEX",
    "index": "registry_index",
    "collection": "registry_records",
    "dim": 1536,
    "distance_metric": "COSINE",
})

# Upsert a document with its embedding
source.execute_query({
    "op": "VECTOR.UPSERT",
    "collection": "registry_records",
    "id": "/source/mydb/database/prod/collection/public/entity/users",
    "doc": {"embedding": [...], "name": "users", "type": "entity", ...},
    "embedding_field": "embedding",
})

# Delete a document (returns the count actually removed: 0 or 1)
source.execute_query({
    "op": "VECTOR.DELETE",
    "collection": "registry_records",
    "id": "...",
})

# List doc ids (optionally only those whose id starts with a prefix)
ids = source.execute_query({
    "op": "VECTOR.LIST_IDS",
    "collection": "registry_records",
    "prefix": "https://example.com/page_",   # optional
})

# Bulk-delete every doc whose id starts with a prefix (returns the count removed).
# Lets a caller clean up a logical group — e.g. a re-ingested page's stale chunks —
# without tracking ids in external state.
removed = source.execute_query({
    "op": "VECTOR.DELETE_BY_PREFIX",
    "collection": "registry_records",
    "prefix": "https://example.com/page_",
})

# KNN search
results = source.execute_query({
    "op": "VECTOR.KNN",
    "index": "registry_index",
    "vector": [...],      # query embedding
    "k": 10,
    "return_fields": ["name", "type", "scope", "description"],
})
# → [{"id": "...", "score": 0.12, "name": "users", ...}, ...]
# score is cosine distance (lower = more similar)
```

### `MemoryVectorSource`

In-memory implementation using a Python dict and numpy cosine distance. No Redis required.

```python
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

vs = MemoryVectorSource()          # name defaults to "memory_vector"
```

### `RedisVectorSource`

Production backend using RedisJSON + RediSearch KNN.

```python
from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource

vs = RedisVectorSource(
    name="my_vector_store",
    properties={
        "connection": {
            "host": "localhost",
            "port": 6379,
            "scan_prefix": "myapp:",   # required — keys are stored as {scan_prefix}{collection}:{id}
        }
    },
)
```

> Requires **Redis Stack** for `FT.CREATE` / `FT.SEARCH`.

---

## `DataSchema`

In-memory graph used by `DataSource` implementations during schema introspection.

```python
from blue_data.core.schema import DataSchema

schema = DataSchema()
```

**Entity methods**

| Method | Returns | Description |
|---|---|---|
| `has_entity(key)` | `bool` | Check if entity exists |
| `add_entity(key)` | `str` | Add entity; appends `__N` suffix on duplicate |
| `add_entity_attribute(key, attribute, type)` | `None` | Add a column/attribute to an entity |
| `get_entities()` | `dict` | All entity definitions |

**Relation methods**

| Method | Returns | Description |
|---|---|---|
| `has_relation(source, relation, target)` | `bool` | Check if relation exists |
| `add_relation(source, relation, target)` | `str` | Add relation; returns unique key |
| `add_relation_attribute(key, property, type)` | `None` | Add a property to a relation |
| `get_relations()` | `dict` | All relation definitions |

---

## `SemanticTypeInferencer`

Deterministic semantic type inference from a list of sample values. No LLM required.

```python
from blue_data.registry.enrichment.semantic_types import SemanticTypeInferencer

inferencer = SemanticTypeInferencer()
result = inferencer.infer(values)
```

**Return shape**:

```python
{
    "semantic_type": "DATE",
    "confidence": 0.95,
    "rationale": "All values match ISO-8601 date pattern.",
    "examples": ["2024-01-15", "2024-02-01"],
}
```

**Detected types**:

| Type | Detected when |
|---|---|
| `BOOLEAN` | All values are `True`/`False` or `"true"`/`"false"` |
| `INTEGER` | All values are Python `int` |
| `FLOAT` | All values are Python `float` |
| `NUMERIC_GENERAL` | Mix of int and float values |
| `DATE` | Values match `YYYY-MM-DD` pattern |
| `DATETIME` | Values match ISO-8601 datetime pattern |
| `TIME` | Values match `HH:MM` / `HH:MM:SS` pattern |
| `EMAIL` | Values match `user@domain` pattern |
| `URL` | Values match `http(s)://...` pattern |
| `IP_ADDRESS` | Values match IPv4/IPv6 pattern |
| `UUID` | Values match UUID pattern |
| `ENUM_CATEGORY` | Low-cardinality string values (≤ max(5, 10% of n) unique values) |
| `STRING` | Short, bounded strings that don't match any pattern |
| `FREE_TEXT` | Long, high-cardinality text values |
| `UNKNOWN` | Values are `None` / empty / unclassifiable |

---

## `MetaData`

LLM-augmented enrichment pipeline. Adds rich semantic signals to entity and attribute records. Deterministic signals run without any LLM; LLM-dependent signals silently return `None` when `llm_fn` is not set.

```python
from blue_data.registry.enrichment.metadata import MetaData

# Deterministic only
enricher = MetaData(llm_fn=None)

# LLM-augmented (any callable str → str)
enricher = MetaData(llm_fn=my_llm_callable)
```

**Constructor parameters**:

| Parameter | Type | Description |
|---|---|---|
| `llm_fn` | `Callable[[str], str] \| None` | Function that sends a prompt and returns a text response. Provider-agnostic — pass Anthropic SDK, OpenAI, a local model, or a test stub. |
| `properties` | `dict` | Override default pipeline feature flags (e.g. `{"enable_semantic_links_inference": False}`) |

**Main entry point**:

```python
enricher.collect_source_metadata(
    data_registry: DataRegistry,
    source: str,
    recursive: bool = True,
    rebuild: bool = False,
)
```

Called automatically by `DataRegistry.enrich_source_metadata`. Rarely called directly.

**Enrichment properties written to attribute records**:

| Property key | Layer | Description |
|---|---|---|
| `value_semantics` | Deterministic / LLM | Semantic type, flags (`is_identifier`, `is_categorical`, etc.), numeric and temporal sub-info |
| `semantic_role` | Deterministic | Structural role: `IDENTIFIER`, `EVENT_TIME`, `SEGMENTATION_DRIVER`, `EVIDENCE`, `DESCRIPTIVE`, etc. |
| `quantitative_vst` | Deterministic | Quantitative role: `MEASUREMENT`, `MAGNITUDE`, `COUNT`, `RATE`, `COMPUTATIONAL`, etc. |
| `process_vst_role` | Deterministic | Role within a process/event log: `PROCESS_KEY`, `EVENT_TIME`, `EVENT_MEASURE`, `STATE_VARIABLE` |
| `semantic_discovery` | LLM | Open-world subcategory and confidence score |
| `domain_concept` | LLM | Canonical domain concept mapping |
| `interpretive_semantics` | LLM | Human-readable value interpretation (ordinal order, severity tiers, etc.) |

**Enrichment properties written to entity records**:

| Property key | Layer | Description |
|---|---|---|
| `semantic_links` | Deterministic | Validated inter-attribute relationships (functional dependency, segmentation, temporal alignment) |
| `process_semantics` | Deterministic | Whether rows represent events; which column is the event time axis |
| `process_patterns` | Deterministic | Temporal cadence and periodicity signals |
| `process_trends` | Deterministic | Trend direction per measure |
| `conditional_value_distribution` | Deterministic | P(value \| group) per categorical × numeric pair |

**`rebuild` behaviour**: when `rebuild=False` (default), LLM-dependent properties that already exist are not overwritten. When `rebuild=True`, all properties are recomputed even if they already exist. Deterministic properties always run regardless of `rebuild`.

---

## `SQLiteDBSource`

Fully implemented `DataSource` for SQLite.

```python
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

SQLiteDBSource(name: str, properties: dict | None = None)
```

**Connection properties** (under `properties["connection"]`):

| Key | Default | Description |
|---|---|---|
| `database_directory` | `"."` | Directory where `.db` files are stored |

**Behaviour notes**

- `fetch_database_collections` always returns `["public"]` — SQLite has no schema concept.
- `fetch_database_collection_relations` always returns `{}`.
- `execute_query` returns results as `list[dict]`. Pass `optional_properties={"commit": True}` for DML.
- `create_database_collection_entity` accepts `cols_definition`, `primary_key`, `foreign_keys` in `properties`.

**Property stats shape**:

```python
{
    "count": 950,
    "distinct_count": 43,
    "null_count": 50,
    "sample_values": ["alice", "bob", ...],
    "min": None,
    "max": None,
}
```

---

## `PostgresDBSource`

Fully implemented `DataSource` for PostgreSQL.

```python
from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource

PostgresDBSource(name: str, properties: dict | None = None)
```

**Connection properties** (under `properties["connection"]`):

| Key | Default | Description |
|---|---|---|
| `host` | `"localhost"` | PostgreSQL host |
| `port` | `5432` | PostgreSQL port |
| `user` | `"postgres"` | Database user |
| `password` | `""` | Database password |
| `database` | `"postgres"` | Default database to connect to |

**Behaviour notes**

- `fetch_databases` lists all databases visible to the user (excluding system DBs).
- `fetch_database_collections` returns schema names from `information_schema.schemata`.
- `fetch_database_collection_entities` builds a `DataSchema` from `information_schema.columns`.
- `fetch_database_collection_relations` reads FK constraints from `information_schema.key_column_usage`.
- `fetch_entity_stats` returns `row_count` via `pg_class.reltuples`.
- `fetch_property_stats` returns `count`, `distinct_count`, `null_count`, `sample_values`, `min`, `max`, and `most_common_vals` from `pg_stats`.

**Property stats shape**:

```python
{
    "count": 1000,
    "distinct_count": 43,
    "null_count": 0,
    "sample_values": ["alice", "bob", ...],
    "min": "alice",
    "max": "zara",
    "most_common_vals": ["alice", "bob"],
}
```

> Requires `psycopg2-binary`: `pip install psycopg2-binary`

---

## Utilities

```python
from blue_data.core.utils.utils import deep_merge
```

| Function | Description |
|---|---|
| `deep_merge(base: dict, update: dict) → dict` | Recursively merge `update` into `base`. Nested dicts are merged; other values are overwritten. Does not mutate `base`. |
