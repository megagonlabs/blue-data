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

- **`Plan` / `PlanNode` / `PlanEdge`** (`plan.py`) — DAG model for execution plans. Nodes have types (`INPUT`, `OUTPUT`, `OPERATOR`) and a status lifecycle (`INITED → REFINING → REFINED → EXECUTING → EXECUTED`). `Plan.to_dict()` serializes the full graph.

- **`Operator`** (`operator.py`) — abstract base with a single `execute(inputs)` method. Concrete operators implement data transformation steps that operate within a `Plan`.

### Storage backends (`blue_data/sources/`)

These serve as the persistence layer for the `Registry`, not for the data sources themselves:

- **`JSONSource`** (`json_source.py`) — ABC with `get(path)`, `set(path, value)`, `delete(path)`.
- **`MemoryJSONSource`** — in-memory dict; default for dev/test.
- **`RedisJSONSource`** — intended production backend; not yet implemented (all methods raise `NotImplementedError`).

Data source implementations are also in this module:
- **`SQLiteDBSource`** — fully implemented; stores `.db` files in a configurable directory. SQLite has no schema concept, so `fetch_database_collections` always returns `["public"]`.
- **`PostgresDBSource`** — stub only.

### DataRegistry (`blue_data/registry/data_registry.py`)

`DataRegistry` extends `Registry` and adds:
1. A `sources` dict mapping names to live `DataSource` objects.
2. Typed hierarchy helpers that map the path convention: `source → database → collection → entity/relation → attribute`.
3. **`sync_source(source, recursive=False)`** — walks a `DataSource`'s live structure and registers everything into the registry. With `recursive=True` it descends through databases → collections → entities/attributes/relations.
4. **`collect_*_stats()`** methods — fetch stats from the data source and write them back as a `"stats"` property on the corresponding registry record.

### Key design conventions

- Registry record paths follow `/{scope}/{type}/{name}`. Scope encodes the full ancestry: e.g., an entity's scope is `/source/{s}/database/{db}/collection/{c}`.
- Stats and metadata are stored as properties on registry records (`"stats"` and `"metadata"` keys), not as separate record types.
- `DataSource` (external data) and `JSONSource` (registry state) are distinct hierarchies that should not be confused.
