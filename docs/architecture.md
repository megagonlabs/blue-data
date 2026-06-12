# Architecture

## Overview

`blue-data` is a data intelligence layer built around two independent abstraction hierarchies that compose together in `DataRegistry`.

```
┌──────────────────────────────────────────────────────────────┐
│                       DataRegistry                           │
│  (extends Registry, adds live-source ops + search)           │
│                                                              │
│   sources: { name → DataSource }                             │
│   store:   JSONSource   (registry state)                     │
│   search_engine: RegistrySearch  (BM25 + vector hybrid)      │
└────────────┬───────────────────────┬─────────────────────────┘
             │                       │
  ┌──────────▼──────────┐  ┌─────────▼──────────────────────┐
  │     DataSource      │  │           Registry              │
  │  (external data)    │  │  (generic key/value catalog)    │
  └──────────┬──────────┘  └─────────┬──────────────────────┘
             │                       │
  ┌──────────▼──────────┐  ┌─────────▼──────────┐
  │  SQLiteDBSource     │  │   JSONSource (ABC)  │
  │  PostgresDBSource   │  │  MemoryJSONSource   │
  │  RedisSource        │  │  RedisJSONSource    │
  │  Neo4jGraphSource   │  └────────────────────-┘
  │  ...                │
  └─────────────────────┘

  Vector search backend (injected into RegistrySearch):

  ┌─────────────────────┐
  │   VectorSource      │
  │  MemoryVectorSource │  ← dev / test
  │  RedisVectorSource  │  ← production (Redis Stack)
  └─────────────────────┘
```

**DataSource hierarchy** — adapters for external data stores. They read and write to databases/files but know nothing about the registry.

**JSONSource / Registry hierarchy** — a persistent key/value store that holds catalog records describing data sources and their contents.

**VectorSource hierarchy** — pluggable vector index used by the search engine. Separate from both `DataSource` and `JSONSource`.

`DataRegistry` bridges all three: it holds live `DataSource` objects in `self.sources`, persists catalog records via `JSONSource`, and indexes them for search via `VectorSource`.

---

## Registry record model

Every piece of catalog knowledge is stored as a **record**. Records are stored in the `JSONSource` under a path key:

```
{scope}/{type}/{name}
```

| Level | type | Example path |
|---|---|---|
| Source | `source` | `/source/sqlite` |
| Database | `database` | `/source/sqlite/database/mydb` |
| Collection | `collection` | `/source/sqlite/database/mydb/collection/public` |
| Entity | `entity` | `/source/sqlite/database/mydb/collection/public/entity/users` |
| Attribute | `attribute` | `/source/sqlite/database/mydb/collection/public/entity/users/attribute/id` |
| Relation | `relation` | `/source/sqlite/database/mydb/collection/public/relation/users_orders` |

Every record is a dict with these standard fields:

```python
{
    "name": "users",
    "type": "entity",
    "scope": "/source/sqlite/database/mydb/collection/public",
    "description": "",
    "created_by": None,
    "icon": None,
    "properties": {},   # arbitrary key/value metadata
    "contents": {},     # unused in records; populated during schema export
}
```

Stats and schema metadata are stored as properties on the corresponding record:

```python
record["properties"]["stats"]    = {"row_count": 1000}
record["properties"]["schema"]   = "..."
record["properties"]["metadata"] = {...}
```

---

## Data flow: sync

`sync_source(source, recursive=True)` walks the live DataSource and reconciles the registry.

```
sync_source
  └─ for each database:
       sync_source_database
         └─ for each collection:
              sync_source_database_collection
                ├─ fetch entities from source
                ├─ compute adds / removes / merges vs registry
                ├─ register / deregister / update entity records
                ├─ register / deregister / update attribute records
                ├─ fetch relations from source
                ├─ register / deregister / update relation records
                ├─ register / deregister / update relation-attribute records
                └─ write schema JSON to collection "schema" property
```

Sync is **idempotent** — running it twice produces the same result.

---

## Data flow: stats collection

Stats are fetched from the live source and written back to registry record properties.

```
collect_source_stats (recursive)
  ├─ collect_source_database_stats     → database.properties["stats"]
  ├─ collect_source_database_collection_stats  → collection.properties["stats"]
  ├─ collect_source_database_collection_entity_stats  → entity.properties["stats"]
  └─ collect_source_database_collection_entity_attribute_stats
                                       → attribute.properties["stats"]
```

Stats shape varies by level:
- **database**: `size_bytes`, `table_count`
- **collection**: `num_entities`, `num_relations`
- **entity**: `row_count`
- **attribute**: `count`, `distinct_count`, `null_count`, `sample_values`, `min`, `max`

---

## Data flow: enrichment

`enrich_source(source)` runs semantic type inference on every attribute's sample values and stores the result as `attribute.properties["value_semantics"]`.

```
enrich_source
  └─ for each database → collection → entity → attribute:
       sample_values = attribute.properties["stats"]["sample_values"]
       result = SemanticTypeInferencer.infer(sample_values)
       attribute.properties["value_semantics"] = result
```

Inference is deterministic and works on Python value types only (no LLM calls). Detected types: `BOOLEAN`, `INTEGER`, `NUMERIC_GENERAL`, `STRING`, `UNKNOWN`.

---

## Data flow: search

`search_records(query, ...)` runs a three-component hybrid search over all registry records.

```
search_records(query)
  └─ RegistrySearch.hybrid_search
       ├─ BM25 pass: score each record's name + description text
       ├─ Vector pass: score_record → KNN lookup in VectorSource
       ├─ combine_scores(bm25_weight, vector_weight, value_weight)
       ├─ apply thresholds (bm25_threshold, vector_threshold, combined_threshold)
       └─ return top-k ranked results
```

Records are indexed into `VectorSource` on every `register_record` / `update_record` call (when `rebuild=True`). The index is rebuilt in bulk after `load()` / `loads()`.

**Search pipeline classes** (`registry/search/`):

| Class | Role |
|---|---|
| `RegistrySearch` | Top-level wiring: holds `HybridSearch` + `RecordIndexer` |
| `HybridSearch` | Orchestrates BM25 + vector scoring and threshold filtering |
| `VectorSearch` | Embedding computation and KNN via `VectorSource` |
| `RecordIndexer` | Keeps `VectorSource` index in sync (upsert / delete) |
| `KeywordSearch` | BM25-only fallback when no `VectorSource` is configured |
| `ranking` | `combine_scores`, `normalize_weights`, `aggregate_value_scores` |

---

## JSONSource backends

| Class | Storage | Use |
|---|---|---|
| `MemoryJSONSource` | Python `dict` | Development, testing |
| `RedisJSONSource` | Redis JSON (RedisJSON module) | Production |

`RedisJSONSource` stores each registry path as a separate Redis key prefixed by a configurable namespace. The `data` property does a SCAN to support `list_records()`.

> Requires **Redis Stack** (`redis-stack-server`) — the `JSON.SET` command is not available in standard Redis.

---

## VectorSource backends

| Class | Storage | Use |
|---|---|---|
| `MemoryVectorSource` | Python `dict` + numpy cosine | Development, testing |
| `RedisVectorSource` | RedisJSON + RediSearch KNN | Production |

Both implement the same `execute_query` interface with operations: `VECTOR.CREATE_INDEX`, `VECTOR.UPSERT`, `VECTOR.DELETE`, `VECTOR.KNN`.

> `RedisVectorSource` also requires **Redis Stack** for `FT.CREATE` and `FT.SEARCH`.

---

## Plan / Operator model

`Plan` is a DAG of `PlanNode` objects used to represent data transformation pipelines. It is independent of the registry hierarchy and exists for future operator-based execution.

```
Plan
  ├─ nodes: { id → PlanNode }
  │           type: INPUT | OUTPUT | OPERATOR
  │           status: INITED → REFINING → REFINED → EXECUTING → EXECUTED
  └─ edges: [ PlanEdge(source_id, target_id) ]
```

`Operator` is the abstract base class for nodes of type `OPERATOR`. Concrete operators implement `execute(inputs) → outputs`.

`Plan.to_dict()` serializes the full graph to a JSON-compatible dict.
