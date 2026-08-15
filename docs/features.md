# Features

## Unified data source interface

Consistent API across heterogeneous backends. Register once, query uniformly.

- **SQL** — SQLite, PostgreSQL, MySQL
- **Document** — MongoDB
- **Graph** — Neo4j

Consistent operations across all: list databases / collections / entities, execute queries, collect stats, introspect schema.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

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

# List what the source contains
print(registry.list_source_databases("sqlite"))
print(registry.list_database_collections("sqlite", "mydb"))
print(registry.list_collection_entities("sqlite", "mydb", "public"))
```

---

## Data registry

A live catalog that mirrors source structure as addressable, searchable records.

- **Hierarchical structure** — databases → collections → entities → attributes
- Each record carries description, properties, statistics, and enriched metadata
- Sync from live sources on demand — incremental or recursive
- Stats collection at every level: row counts, value distributions, sample data

```python
# Sync source structure into the registry
registry.sync_source("sqlite", recursive=True)

# Collect stats at every level
registry.collect_source_database_stats("sqlite", "mydb")
registry.collect_source_database_collection_stats("sqlite", "mydb", "public")
registry.collect_source_database_collection_entity_stats("sqlite", "mydb", "public", "users")
registry.collect_source_database_collection_entity_attribute_stats(
    "sqlite", "mydb", "public", "users", "name"
)
```

---

## Semantic enrichment

Automatically infers meaning from data. No LLM required.

- **Semantic type inference** — detects dates, currencies, identifiers, categories, free text, and more
- **Attribute roles** — classifies each column by its functional role (identifier, time dimension, grouping attribute, measurement)
- **Value axes** — magnitude and ordinal ranges from distributions
- **Process semantics** — detects event tables, temporal cadence, trend direction
- **Quantitative rules** — total/component relationships, safe aggregation guidance, derived metric candidates
- **Semantic links** — statistically validated relationships between attributes

```python
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

# Deterministic-only — no API key needed
enricher = MetaData(llm_fn=None)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)

# Prerequisites must be run in order
registry.sync_all(recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
```

See `examples/feature-demos/enrichment_demo.py` for a deep-dive including standalone `SemanticTypeInferencer` usage, idempotency, and rebuild behavior.

---

## LLM-augmented metadata

When paired with an LLM (Anthropic, OpenAI, or any provider), generates natural-language descriptions, domain concept mappings, and interpretive semantics.

```python
import anthropic
from blue_data.registry.enrichment.metadata import MetaData

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def llm_fn(prompt: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""

enricher = MetaData(llm_fn=llm_fn)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)
```

`llm_fn` is provider-agnostic — any `(str) -> str` callable works. `rebuild=False` (default) is idempotent: existing properties are not overwritten on subsequent calls.

---

## Hybrid search

BM25 keyword + vector similarity search over all registry records, with hierarchical score propagation.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=my_embedding_fn,   # callable: str → list[float]
    vector_dim=1536,
    rebuild=True,
)

results = registry.search_records("user accounts")
for r in results:
    print(r["name"], r.get("_score"))
```

Omit `vector_source` and `embedding_fn` to fall back to keyword-only search. Search weights and thresholds are tunable — see the [Configuration](../README.md#configuration) section.

---

## Natural language querying

Translates natural language questions into native queries via pluggable LLM functions. Supported dialects: SQL (SQLite, PostgreSQL, MySQL), Cypher (Neo4j), MongoDB filters, and vector KNN (MemoryVectorSource, ChromaDB, Redis, File).

**SQL and graph sources** — schema context from the registry is automatically injected into the LLM prompt:

```python
rows = registry.execute_query_nl(
    "mydb",
    "show me all orders over $100",
    database="sales",
    collection="public",
)
```

**Vector sources** — no LLM needed; the query is embedded and run as KNN:

```python
results = registry.execute_query_nl(
    "docs",
    "documents about machine learning",
    collection="docs",
    optional_properties={"k": 10},
)
```

---

## Data import and export

Move rows between registered sources, or export them directly to a file — no manual pandas or SQL boilerplate required.

### `import_data` — source to source

Copies rows from one registered DataSource into another. The transfer is **pull-based**: the target connects to the source and reads from it.

```python
registry.import_data(
    source="csv_store",    # registered name of the source to read from
    target="sqlite_store", # registered name of the target to write into
    database="shop",       # target database
    collection="orders",   # identifies the collection on the source side
    entity="orders",       # target table/entity name (required for SQL targets)
    mode="append",         # "append" (default) or "overwrite"
)
```

**`collection` vs `entity`**

These two parameters serve different sides of the transfer:

| Parameter | Side | Meaning |
|---|---|---|
| `collection` | Source | Which collection to read from (file stem for FileSource, table name for SQL sources) |
| `entity` | Target | Which table to write into on the SQL target |

They are separate because source and target may use different names for the same data. For `FileSource` targets, `entity` is not needed — the output filename is derived from `collection`.

**Source compatibility**

Any source that returns a flat list of rows from `execute_query(None, collection=...)` can be used as the source:

| Source type | Can be source | Can be target |
|---|---|---|
| `FileSource` | Yes | Yes |
| `SQLiteDBSource` | Yes | Yes |
| `PostgresDBSource` | Yes | Yes |
| `MySQLDBSource` | Yes | Yes |
| `GraphSource` | No — `execute_query` expects dict ops, not `None` | No |
| `VectorSource` | No | No |

**Modes**

- `"append"` — adds rows to existing data without touching what is already there.
- `"overwrite"` — clears the target table or file first, then writes the new rows.

**Examples**

File → SQL:
```python
registry.import_data(
    source="csv_store",
    target="sqlite_store",
    database="shop",
    collection="customers",  # reads customers.csv
    entity="customers",      # writes into the customers table
    mode="append",
)
```

SQL → SQL (same database name, different directories):
```python
registry.import_data(
    source="analytics_store",
    target="warehouse_store",
    database="shop",
    collection="top_customers",  # source table
    entity="top_customers",      # target table
    mode="append",
)
```

File → File (no `entity` needed):
```python
registry.import_data(
    source="csv_store",
    target="csv_backup",
    collection="orders",
    mode="append",
)
```

See `examples/feature-demos/import_data_demo.py` for a full walkthrough including overwrite mode and SQL → SQL transfer.

---

### `export_data` — source to file

Exports rows from a registered source directly to a file. Format is inferred from the file extension, or can be forced with `fmt`.

```python
registry.export_data(
    source="sqlite_store",          # registered source to read from
    path="/tmp/exports/orders.csv", # output file path
    database="shop",
    collection="orders",            # table or file to export
    query=None,                     # None = all rows; SQL string or dict = filter
    fmt=None,                       # inferred from extension: csv, json, jsonl, parquet
)
```

**Supported formats:** `csv`, `json`, `jsonl`, `parquet` — inferred from the file extension, or set explicitly with `fmt`.

**Filtering:** pass a query to export a subset of rows. For SQL sources this is a SQL string; for `FileSource` it is a `{column: value}` equality filter.

```python
# Export only paid orders to JSONL
registry.export_data(
    source="sqlite_store",
    path="/tmp/exports/paid_orders.jsonl",
    database="shop",
    collection="orders",
    query="SELECT * FROM orders WHERE status = 'paid'",
)
```

`export_data` is a registry-level convenience — there is no `DataSource.export_data` method. It always reads via `execute_query` and writes using pandas.

See `examples/feature-demos/export_data_demo.py` for a full walkthrough including CSV, JSON, and filtered JSONL exports.

---

## MCP server

Exposes registry operations as tools for Claude and other MCP clients, enabling AI agents to explore and query your data autonomously.

```bash
# Start the MCP server (stdio transport)
blue-data-registry-mcp

# With a pre-loaded source config
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp
```

**Claude Desktop config:**

```json
{
  "mcpServers": {
    "blue-data-registry": {
      "command": "blue-data-registry-mcp",
      "env": {
        "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json"
      }
    }
  }
}
```

See [`docs/registry-mcp.md`](registry-mcp.md) for the full tool reference.

---

## REST API and CLI

Full platform layer for production deployments and scripting.

**REST API:**

```bash
blue-data-api  # starts on http://localhost:8000
# interactive docs at http://localhost:8000/docs
```

**CLI:**

```bash
blue-data sources add shop --type sqlite --database-dir /data/shop
blue-data sync shop
blue-data stats shop
blue-data enrich shop
blue-data search "revenue"
blue-data inspect entity shop mydb public orders
```

See [`docs/api.md`](api.md) and [`docs/cli.md`](cli.md) for full references.
