# API Reference

## `blue_data.core.source.DataSource`

Base class for all data source adapters. Subclasses override only the methods they support; the defaults return empty results without raising.

```python
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

## `blue_data.core.registry.Registry`

Generic key/value catalog backed by a `JSONSource`. All records are addressable by `(name, type, scope)`.

```python
Registry(name: str = "REGISTRY", store: JSONSource | None = None)
```

**Record CRUD**

| Method | Returns | Description |
|---|---|---|
| `register_record(name, type, scope, description, properties, created_by, icon)` | `dict` | Create and store a new record |
| `get_record(name, type, scope)` | `dict \| None` | Retrieve a record by identity |
| `update_record(name, type, scope, description, properties, icon)` | `tuple \| dict` | Upsert a record, merging properties |
| `deregister_record(name, type, scope)` | `None` | Delete a record |
| `deregister(record)` | `None` | Delete using a record dict |
| `list_records(record_type, scope, recursive)` | `list[dict]` | Query records by type/scope |
| `filter_record_contents(name, type, scope, filter_type, filter_name, single)` | `list[dict]` | Find child records under a parent path |

**Properties**

| Method | Returns | Description |
|---|---|---|
| `get_record_properties(name, type, scope)` | `dict` | All properties on a record |
| `get_record_property(name, type, scope, key)` | `Any` | Single property value |
| `set_record_property(name, type, scope, key, value)` | `dict` | Set a property |
| `delete_record_property(name, type, scope, key)` | `Any` | Remove a property, returns old value |
| `get_record_description(name, type, scope)` | `str \| None` | Description field |
| `set_record_description(name, type, scope, description)` | `dict` | Set description field |

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
| `register_record_json(record, recursive)` | Register a record dict (and optionally its nested `contents`) |

---

## `blue_data.registry.data_registry.DataRegistry`

Extends `Registry` with live-source operations. The central class for most use.

```python
DataRegistry(name: str = "DATA_REGISTRY", store: JSONSource | None = None)
```

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `sources` | `dict[str, DataSource]` | Live source objects by name |
| `semantic_type_inferencer` | `SemanticTypeInferencer` | Used by `enrich_source` |

### Source management

| Method | Description |
|---|---|
| `register_source(source)` | Register a `DataSource` and write its top-level record |
| `get_source(name)` | Return the live `DataSource` for `name` |
| `list_sources()` | Names of all registered sources |
| `deregister_source(source)` | Remove source object and its registry record |
| `connect_source(source)` | Return the live source object, reconstructing from properties if needed |
| `execute_query(source, query, database, collection, optional_properties)` | Delegate query to the named source |

### Hierarchy helpers

These are typed wrappers around `register_record` / `get_record` / `list_records` / `update_record` / `deregister_record`. The full list follows the pattern `{verb}_source_database[_collection[_entity[_attribute]]]`.

**Register**
```python
register_source_database(source, database, description, properties)
register_source_database_collection(source, database, collection, ...)
register_source_database_collection_entity(source, database, collection, entity, ...)
register_source_database_collection_entity_attribute(source, database, collection, entity, attribute, ...)
register_source_database_collection_relation(source, database, collection, relation, ...)
register_source_database_collection_relation_attribute(source, database, collection, relation, attribute, ...)
```

**Get**
```python
get_source_database(source, database)
get_source_database_collection(source, database, collection)
get_source_database_collection_entity(source, database, collection, entity)
get_source_database_collection_entity_attribute(source, database, collection, entity, attribute)
get_source_database_collection_relation(source, database, collection, relation)
```

**List**
```python
list_source_databases(source)
list_database_collections(source, database)
list_collection_entities(source, database, collection)
list_entity_attributes(source, database, collection, entity)
list_collection_relations(source, database, collection)
get_source_database_collection_relation_attributes(source, database, collection, relation)
```

**Update / Deregister** — same naming pattern as above.

### Property and description helpers

Every level in the hierarchy has `get_*_property`, `set_*_property`, `get_*_description`, `set_*_description` variants. Examples:

```python
set_source_database_property(source, database, key, value)
get_source_database_collection_entity_attribute_property(source, db, col, entity, attr, key)
set_source_database_collection_entity_description(source, db, col, entity, description)
```

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

Fetch stats from the live source and persist as `"stats"` property on the corresponding record.

| Method | Persists to |
|---|---|
| `collect_source_stats(source, recursive=False)` | Source record + optionally all descendants |
| `collect_source_database_stats(source, database)` | Database record |
| `collect_source_database_collection_stats(source, database, collection)` | Collection record |
| `collect_source_database_collection_entity_stats(source, database, collection, entity)` | Entity record |
| `collect_source_database_collection_entity_attribute_stats(source, database, collection, entity, attribute)` | Attribute record |
| `collect_entity_stats(source, database, collection, entity)` | Shorthand for entity-level |
| `collect_attribute_stats(source, database, collection, entity, attribute)` | Shorthand for attribute-level |
| `collect_relation_stats(source, database, collection, relation)` | Relation record |

### Semantic enrichment

| Method | Description |
|---|---|
| `enrich_source_database_collection_entity_attribute(source, db, col, entity, attr)` | Infer semantic type from `stats.sample_values` and write to attribute `"semantic_type"` property |
| `enrich_source(source)` | Enrich all attributes for all entities across all collections |

### Create operations

These call the live source's `create_*` method and then sync the registry.

| Method | Description |
|---|---|
| `create_source_database(source, database, properties, overwrite, recursive)` | Create database and sync |
| `create_source_database_collection(source, database, collection, properties, overwrite, recursive)` | Create collection and sync |
| `create_source_database_collection_entity(source, database, collection, entity, properties, creation_properties, overwrite, recursive)` | Create entity (table), auto-register missing parents, sync |
| `create_source_database_collection_relation(source, database, collection, relation, properties, overwrite, recursive)` | Create relation and sync |

`creation_properties` are passed to the source's `create_*` call. `properties` are written to the registry record after sync. Returns `None` if the item exists and `overwrite=False`.

### Schema export

| Method | Returns | Description |
|---|---|---|
| `get_data_source_schema(source, database, collection, format="dict")` | `dict \| str` | Export entity+relation schema. `format` can be `"dict"`, `"json"`, or `"yaml"` |

### Search

| Method | Returns | Description |
|---|---|---|
| `search_records(query, record_type, scope, recursive)` | `list[dict]` | Full-text search across name, type, scope, description, and properties |

---

## `blue_data.core.schema.DataSchema`

In-memory graph used by `DataSource` implementations to build their entity/relation structure during introspection.

```python
DataSchema()
```

**Entity methods**

| Method | Returns | Description |
|---|---|---|
| `has_entity(key)` | `bool` | Check if entity exists |
| `add_entity(key)` | `str` | Add entity; appends `__N` suffix on duplicate |
| `add_entity_property(key, attribute, type)` | `None` | Add a column/attribute to an entity |
| `get_entities()` | `dict` | All entity definitions |

**Relation methods**

| Method | Returns | Description |
|---|---|---|
| `has_relation(source, relation, target)` | `bool` | Check if relation exists |
| `add_relation(source, relation, target)` | `str` | Add relation; returns unique key |
| `add_relation_property(key, property, type)` | `None` | Add a property to a relation |
| `get_relations()` | `dict` | All relation definitions |

**Serialization**

| Method | Returns | Description |
|---|---|---|
| `to_json()` | `dict` | `{"entities": {...}, "relations": {...}}` |
| `__str__()` | `str` | Human-readable schema dump |

Relation keys are encoded as `source__relation__target`. Duplicate relations get `__N` suffixes.

---

## `blue_data.core.plan`

DAG model for execution plans.

### `NodeStatus` (str Enum)

`INITED` → `REFINING` → `REFINED` → `EXECUTING` → `EXECUTED`, plus `PLANNED` and `FAILED`.

### `NodeType` (str Enum)

`INPUT`, `OUTPUT`, `OPERATOR`.

### `PlanNode` (dataclass)

| Field | Type | Default |
|---|---|---|
| `id` | `str` | required |
| `type` | `NodeType` | required |
| `label` | `str \| None` | `None` |
| `value` | `Any` | `None` |
| `status` | `NodeStatus` | `INITED` |
| `properties` | `dict` | `{}` |
| `metadata` | `dict` | `{}` |

### `PlanEdge` (dataclass)

| Field | Type |
|---|---|
| `source` | `str` (node id) |
| `target` | `str` (node id) |
| `properties` | `dict` |

### `Plan` (dataclass)

| Field | Type |
|---|---|
| `id` | `str \| None` |
| `label` | `str \| None` |
| `nodes` | `dict[str, PlanNode]` |
| `edges` | `list[PlanEdge]` |
| `input_node_id` | `str \| None` |
| `output_node_id` | `str \| None` |
| `provenance` | `str \| None` |

**Methods**

| Method | Returns | Description |
|---|---|---|
| `add_node(node)` | `PlanNode` | Register a node |
| `add_edge(source_id, target_id, **properties)` | `PlanEdge` | Add a directed edge |
| `get_node(node_id)` | `PlanNode \| None` | Lookup node by id |
| `set_input(node_id)` | `None` | Designate the input node |
| `set_output(node_id)` | `None` | Designate the output node |
| `to_dict()` | `dict` | Full JSON-serializable representation |

---

## `blue_data.core.operator.Operator`

Abstract base class for transformation operators.

```python
class Operator(ABC):
    @abstractmethod
    def execute(self, inputs) -> Any: ...
```

---

## `blue_data.sources.sqlite_source.SQLiteDBSource`

Fully implemented `DataSource` for SQLite.

```python
SQLiteDBSource(name: str, properties: dict | None = None)
```

**Connection properties** (under `properties["connection"]`):

| Key | Default | Description |
|---|---|---|
| `database_directory` | `"."` | Directory where `.db` files are stored |
| `host` | `"localhost"` | Unused by SQLite; present for interface parity |
| `port` | `5432` | Unused |
| `protocol` | `"sqlite"` | Unused |

**Behaviour notes**

- `fetch_database_collections` always returns `["public"]` — SQLite has no schema concept.
- `fetch_database_collection_relations` always returns `{}` — foreign key parsing is not implemented.
- `create_database_collection_relation` returns `{"status": "skipped"}` — SQLite cannot add FKs after table creation.
- `execute_query` converts results to pandas `DataFrame`, then to `list[dict]` via `df.to_json(orient="records")`. Pass `optional_properties={"commit": True}` for DML statements.
- `create_database_collection_entity` accepts `properties` with `cols_definition`, `primary_key`, and `foreign_keys`:

```python
properties = {
    "cols_definition": [
        {"name": "id",   "type": "INTEGER", "misc": "NOT NULL"},
        {"name": "name", "type": "TEXT"},
    ],
    "primary_key": ["id"],
    "foreign_keys": [
        {
            "foreign_keys_source_columns": ["order_id"],
            "foreign_keys_target_table":   "orders",
            "foreign_keys_target_columns": ["id"],
        }
    ],
}
```

**Property stats shape** (`fetch_property_stats`):

```python
{
    "count": 950,
    "distinct_count": 43,
    "null_count": 50,
    "sample_values": ["alice", "bob", ...],
    "min": None,   # populated only for INT/REAL/NUM/DATE/TIME columns
    "max": None,
    "most_common_vals": [],  # not supported by SQLite
}
```

---

## `blue_data.sources.json_source.JSONSource`

Abstract base for the registry's storage backend.

```python
class JSONSource(ABC):
    def get(self, path: str) -> Any: ...
    def set(self, path: str, value: Any) -> None: ...
    def delete(self, path: str) -> None: ...
```

### `MemoryJSONSource`

In-memory implementation backed by a plain `dict`. Default when no store is passed to `Registry`.

### `RedisJSONSource`

Stub. All methods raise `NotImplementedError`. Intended as the production backend.

---

## `blue_data.enrichment.value_semantics.semantic_types.SemanticTypeInferencer`

Deterministic semantic type inference from a list of sample values.

```python
inferencer = SemanticTypeInferencer()
result = inferencer.infer(values)
```

**Return shape**:

```python
{
    "semantic_type": "INTEGER",  # BOOLEAN | INTEGER | NUMERIC_GENERAL | STRING | UNKNOWN
    "confidence": 0.7,           # 0.0 if UNKNOWN (no values), 0.7 otherwise
    "rationale": "Inferred from simple Python value types.",
    "examples": [1, 2, 3, 4, 5],
}
```

Inference rules (evaluated in order):
1. All `bool` → `BOOLEAN`
2. All `int` (non-bool) → `INTEGER`
3. All `int | float` (non-bool) → `NUMERIC_GENERAL`
4. All `str` → `STRING`
5. Otherwise → `UNKNOWN`

---

## `blue_data.core.utils`

| Function | Description |
|---|---|
| `deep_merge(base: dict, update: dict) → dict` | Recursively merge `update` into `base`. Nested dicts are merged; other values are overwritten. |
