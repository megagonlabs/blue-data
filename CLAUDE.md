# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip install -e .
```

The package has two runtime dependencies: `pandas` and `numpy`. No build step is required.

## Architecture

`blue-data` is a data intelligence layer with two independent abstraction hierarchies that compose together in `DataRegistry`.

### Core abstractions (`blue_data/core/`)

- **`DataSource`** (`source.py`) — base interface all data sources implement. Methods follow a consistent naming pattern: `fetch_*` for reads, `create_*` for writes, `execute_query` for ad-hoc queries, and `fetch_*_stats` for statistics. Subclasses override only the methods they support.

- **`Registry`** (`registry.py`) — generic key/value store for records, backed by a `JSONSource`. Records are keyed by the path `{scope}/{type}/{name}` (e.g., `/source/sqlite/database/mydb`). The root key `$` holds top-level metadata.

- **`DataSchema`** (`schema.py`) — in-memory graph model used by `DataSource` implementations during schema introspection. Holds entities (with attributes) and relations. Sources build a `DataSchema`, call `get_entities()`, and return the result from `fetch_database_collection_entities`.

### Storage backends (`blue_data/sources/`)

These serve as the persistence layer for the `Registry`, not for the data sources themselves:

- **`JSONSource`** (`json_source.py`) — ABC with `get(path)`, `set(path, value)`, `delete(path)`.
- **`MemoryJSONSource`** — in-memory dict; default for dev/test.
- **`RedisJSONSource`** — production backend; fully implemented. Stores each registry path as a separate Redis key prefixed by a namespace. Requires Redis Stack (`redis-stack-server`) for `JSON.SET`/`JSON.GET`.

Data source implementations are also in this module:
- **`SQLiteDBSource`** — fully implemented; stores `.db` files in a configurable directory. SQLite has no schema concept, so `fetch_database_collections` always returns `["public"]`.
- **`PostgresDBSource`** — stub only.

### VectorSource (`lib/src/blue-data/source/vector/`)

Pluggable vector index used by the search engine. Separate from both `DataSource` and `JSONSource`.

- **`MemoryVectorSource`** — in-memory dict + numpy cosine distance; for dev/test. No Redis required.
- **`RedisVectorSource`** — production backend using RedisJSON + RediSearch KNN. Requires Redis Stack.

All backends implement `execute_query` with ops: `VECTOR.CREATE_INDEX`, `VECTOR.UPSERT`, `VECTOR.DELETE`, `VECTOR.KNN`.

### DataRegistry (`lib/src/blue-data/registry/data_registry.py`)

`DataRegistry` extends `Registry` and adds:
1. A `sources` dict mapping names to live `DataSource` objects.
2. Typed hierarchy helpers that map the path convention: `source → database → collection → entity/relation → attribute`.
3. **`sync_source(source, recursive=False)`** — walks a `DataSource`'s live structure and registers everything into the registry. With `recursive=True` it descends through databases → collections → entities/attributes/relations.
4. **`collect_*_stats()`** methods — fetch stats from the data source and write them back as a `"stats"` property on the corresponding registry record.
5. **`search_records(query, ...)`** — hybrid BM25 + vector search over all registry records, implemented in `registry/search/`.

### Search pipeline (`lib/src/blue-data/registry/search/`)

`RegistrySearch` wires `HybridSearch` (BM25 + vector scoring) and `RecordIndexer` (keeps `VectorSource` in sync). `_on_record_changed` / `_on_record_deleted` hooks in `Registry` trigger indexing on every write when `rebuild=True`.

### Key design conventions

- Registry record paths follow `/{scope}/{type}/{name}`. Scope encodes the full ancestry: e.g., an entity's scope is `/source/{s}/database/{db}/collection/{c}`.
- Stats and metadata are stored as properties on registry records (`"stats"` and `"metadata"` keys), not as separate record types.
- `DataSource` (external data), `JSONSource` (registry state), and `VectorSource` (search index) are three distinct hierarchies that should not be confused.
- The `rebuild` parameter on Registry write methods is a three-state flag: `True` = force index, `False` = suppress index, `None` = defer to `DataRegistry._rebuild` instance default.
