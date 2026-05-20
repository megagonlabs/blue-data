# blue-data

Blue Data Intelligence Layer — a Python library for registering, introspecting, and querying heterogeneous data sources through a unified interface.

## Installation

```bash
pip install -e .
```

## Concepts

**DataSource** — an adapter for an external data store (SQLite, Postgres, etc.). Each source exposes a consistent interface for listing databases, collections, entities, relations, and executing queries.

**DataRegistry** — a catalog that tracks registered sources and mirrors their structure (databases → collections → entities → attributes) as addressable records. Records can carry metadata, descriptions, properties, and statistics.

**JSONSource** — the storage backend for the registry itself. Defaults to in-memory (`MemoryJSONSource`) for development; `RedisJSONSource` is the intended production backend.

**Plan** — a DAG of `PlanNode` objects (`INPUT`, `OUTPUT`, `OPERATOR`) used to represent and execute data transformation pipelines.

## Quick start

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.sources.sqlite_source import SQLiteDBSource

registry = DataRegistry()

source = SQLiteDBSource(
    name="sqlite",
    properties={
        "connection": {"database_directory": "/tmp/my-data"}
    },
)
registry.register_source(source)

# Create a database and table
source.create_database("mydb")
registry.execute_query(
    source="sqlite",
    database="mydb",
    query="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
    optional_properties={"commit": True},
)

# Sync source structure into the registry
registry.sync_source("sqlite", recursive=True)

# List what was discovered
print(registry.list_source_databases("sqlite"))
print(registry.list_database_collections("sqlite", "mydb"))
print(registry.list_collection_entities("sqlite", "mydb", "public"))
```

## Syncing and stats

```python
# Sync a specific collection
registry.sync_source_database_collection("sqlite", "mydb", "public")

# Collect stats at various levels
registry.collect_source_database_stats("sqlite", "mydb")
registry.collect_source_database_collection_stats("sqlite", "mydb", "public")
registry.collect_source_database_collection_entity_stats("sqlite", "mydb", "public", "users")
registry.collect_source_database_collection_entity_attribute_stats(
    "sqlite", "mydb", "public", "users", "name"
)
```

## Implementing a new DataSource

Subclass `blue_data.core.source.DataSource` and override the methods your backend supports:

```python
from blue_data.core.source import DataSource

class MySource(DataSource):
    def fetch_databases(self) -> list[str]: ...
    def fetch_database_collections(self, database: str) -> list[str]: ...
    def fetch_database_collection_entities(self, database: str, collection: str) -> dict: ...
    def execute_query(self, query, database=None, collection=None, optional_properties=None): ...
```

`fetch_database_collection_entities` should return a dict keyed by entity name. Each value follows the `DataSchema` entity format: `{"properties": {}, "contents": {"attributes": {"col": {"name": "col", "info": {...}}}}}`.
