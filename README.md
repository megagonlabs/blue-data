# blue-data

Blue Data Intelligence Layer — a Python library for registering, introspecting, and querying heterogeneous data sources through a unified interface.

## Installation

```bash
pip install -e .
```

> **Note:** The top-level import package name is pending confirmation. Until then, set `PYTHONPATH` to `lib/src/blue-data` and import modules directly (e.g. `from registry.data_registry import DataRegistry`).

## Runtime dependencies

- `pandas`, `numpy` — always required

Optional extras (install with `pip install -e ".[redis]"` etc.):

| Extra | Packages | Required for |
|---|---|---|
| `redis` | `redis` | `RedisJSONSource`, `RedisVectorSource`, `RedisStreamSource` |
| `postgres` | `psycopg2-binary` | `PostgresDBSource` |
| `mysql` | `mysql-connector-python` | `MySQLDBSource` |
| `mongodb` | `pymongo` | `MongoDBJSONSource` |
| `neo4j` | `neo4j` | `Neo4jGraphSource` |

> **Redis Stack required:** `RedisJSONSource` and `RedisVectorSource` use `JSON.SET` and `FT.CREATE` commands that are not available in standard Redis. You need **Redis Stack** (`redis-stack-server`), not plain `redis`.

## Concepts

**DataSource** — an adapter for an external data store (SQLite, Postgres, Redis, etc.). Each source exposes a consistent interface for listing databases, collections, entities, relations, and executing queries.

**DataRegistry** — a catalog that tracks registered sources and mirrors their structure (databases → collections → entities → attributes) as addressable records. Records carry metadata, descriptions, properties, statistics, and are searchable.

**JSONSource** — the storage backend for the registry itself. Defaults to in-memory (`MemoryJSONSource`) for development; `RedisJSONSource` is the production backend.

**VectorSource** — pluggable vector index used by the search engine. `MemoryVectorSource` for dev/test; `RedisVectorSource` for production (requires Redis Stack).

**Plan** — a DAG of `PlanNode` objects (`INPUT`, `OUTPUT`, `OPERATOR`) used to represent and execute data transformation pipelines.

## Quick start

```python
from registry.data_registry import DataRegistry
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

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

## Search

`DataRegistry` supports hybrid search (BM25 keyword + vector similarity) over all registry records. Pass a `VectorSource` and an embedding function to enable vector search; omit them to fall back to keyword-only.

```python
from registry.data_registry import DataRegistry
from source.json.memory_json_source import MemoryJSONSource
from source.vector.memory_vector_source import MemoryVectorSource

# In-memory search — no Redis required
registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=my_embedding_fn,   # callable: str → list[float]
    vector_dim=1536,
    rebuild=True,
)

registry.register_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Stores user accounts and profile data",
)

results = registry.search_records("user accounts")
for r in results:
    print(r["name"], r.get("_score"))
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

Subclass `DataSource` and override the methods your backend supports:

```python
from source.source import DataSource

class MySource(DataSource):
    def fetch_databases(self) -> list[str]: ...
    def fetch_database_collections(self, database: str) -> list[str]: ...
    def fetch_database_collection_entities(self, database: str, collection: str) -> dict: ...
    def execute_query(self, query, database=None, collection=None, optional_properties=None): ...
```

`fetch_database_collection_entities` should return a dict keyed by entity name. Each value follows the `DataSchema` entity format:

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

## Running tests

```bash
cd lib
PYTHONPATH=src/blue-data python3 -m pytest tests/
```

Redis integration tests (`tests/integration/test_redis_registry.py`) auto-skip when Redis Stack is not running. To run them:

```bash
redis-stack-server --port 6379 --daemonize yes
PYTHONPATH=src/blue-data python3 -m pytest tests/integration/test_redis_registry.py -v
```
