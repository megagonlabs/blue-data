# Architecture

## Overview

`blue-data` is a data intelligence layer built around two independent abstraction hierarchies that compose together in `DataRegistry`.

```
┌─────────────────────────────────────────────────────┐
│                    DataRegistry                     │
│  (extends Registry, adds live-source operations)    │
│                                                     │
│   sources: { name → DataSource }                    │
│   store:   JSONSource  (registry state)             │
└──────────────┬───────────────────────┬──────────────┘
               │                       │
    ┌──────────▼──────────┐  ┌─────────▼──────────┐
    │     DataSource      │  │      Registry       │
    │  (external data)    │  │  (key/value store)  │
    └──────────┬──────────┘  └─────────┬───────────┘
               │                       │
    ┌──────────▼──────────┐  ┌─────────▼───────────┐
    │  SQLiteDBSource     │  │   JSONSource (ABC)   │
    │  PostgresDBSource   │  │  MemoryJSONSource    │
    │  (your source...)   │  │  RedisJSONSource     │
    └─────────────────────┘  └─────────────────────┘
```

**DataSource hierarchy** — adapters for external data stores. They read and write to databases/files but know nothing about the registry.

**JSONSource / Registry hierarchy** — a persistent key/value store that holds catalog records describing data sources and their contents.

`DataRegistry` bridges the two: it holds live `DataSource` objects in `self.sources` and mirrors their structure into the registry via `sync_*` methods.

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

Stats and schema metadata are stored as properties on the corresponding record — not as separate record types:

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

`enrich_source(source)` runs semantic type inference on every attribute's sample values and stores the result as `attribute.properties["semantic_type"]`.

```
enrich_source
  └─ for each database → collection → entity → attribute:
       sample_values = attribute.properties["stats"]["sample_values"]
       result = SemanticTypeInferencer.infer(sample_values)
       attribute.properties["semantic_type"] = result
```

Inference is deterministic and works on Python value types only (no LLM calls). Detected types: `BOOLEAN`, `INTEGER`, `NUMERIC_GENERAL`, `STRING`, `UNKNOWN`.

---

## JSONSource backends

| Class | Storage | Use |
|---|---|---|
| `MemoryJSONSource` | Python `dict` | Development, testing |
| `RedisJSONSource` | Redis JSON | Production (not yet implemented) |

The `Registry` class accepts any `JSONSource` via its `store` parameter, making it straightforward to swap backends.

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
