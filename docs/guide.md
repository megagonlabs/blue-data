# Developer Guide

## Quick start

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

# Sync source structure into the registry
registry.sync_source("sqlite", recursive=True)

# List what was discovered
print(registry.list_source_databases("sqlite"))
print(registry.list_database_collections("sqlite", "mydb"))
print(registry.list_collection_entities("sqlite", "mydb", "public"))
```

---

## Syncing and stats

`sync_source` walks the live source and reconciles its structure into the registry — computing adds, removes, and merges at each level. `recursive=True` descends the full hierarchy in one call.

```python
# Sync the full source hierarchy
registry.sync_source("sqlite", recursive=True)

# Or sync a specific collection
registry.sync_source_database_collection("sqlite", "mydb", "public")

# Collect stats at various levels
registry.collect_source_database_stats("sqlite", "mydb")
registry.collect_source_database_collection_stats("sqlite", "mydb", "public")
registry.collect_source_database_collection_entity_stats("sqlite", "mydb", "public", "users")
registry.collect_source_database_collection_entity_attribute_stats(
    "sqlite", "mydb", "public", "users", "name"
)

# Or collect the full hierarchy in one call
registry.collect_source_stats("sqlite", recursive=True)
```

Stats are stored as the `"stats"` property on each registry record and are consumed by the enrichment pipeline.

---

## Enrichment

blue-data enriches registry records with two layers of intelligence.

**Layer 1 — Deterministic** (`enrich_source`): runs `SemanticTypeInferencer` on every attribute's sample values and writes the detected semantic type to `attribute.properties["value_semantics"]`. No API key or LLM required.

**Layer 2 — MetaData pipeline** (`enrich_source_metadata`): builds on Layer 1 and adds process semantics, semantic roles, value-axis detection, statistical relationship signals, and — when an `llm_fn` is provided — LLM-augmented enrichments (VSI, SDI, domain concept, entity descriptions).

Prerequisites must be run in order — sync first, then collect stats, then enrich:

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

# Deterministic-only (no API key needed)
enricher = MetaData(llm_fn=None)
registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)

registry.sync_all(recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)
```

To enable LLM-augmented enrichment, install `anthropic` (`pip install "blue-data[llm]"`) and pass an `llm_fn`:

```python
import anthropic

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

`llm_fn` is provider-agnostic — any callable `(str) -> str` works (OpenAI, local models, test stubs).

`rebuild=False` is idempotent: existing enrichment properties are not overwritten on subsequent calls. Use `rebuild=True` to force re-enrichment.

---

## Search

`DataRegistry` supports hybrid search (BM25 keyword + vector similarity) over all registry records. Pass a `VectorSource` and an embedding function to enable vector search; omit them to fall back to keyword-only.

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

Search weights and thresholds are tunable via constructor arguments or environment variables — see the [Configuration](../README.md#configuration) section.

---

## Natural language queries

`DataRegistry.execute_query_nl` translates a plain-English question and executes it against a registered source. The translation strategy depends on the source type.

### SQL and graph sources — LLM pipeline

For SQL (SQLite, Postgres, MySQL) and graph (Neo4j) sources the pipeline is:

```
NL query
  → _format_schema_for_nl()    # renders entity/attribute list as text
  → _build_nl_prompt()         # adds dialect-specific instructions ("write a SQL SELECT…")
  → llm_fn(prompt)             # LLM produces the native query
  → _extract_native_query()    # strips markdown fences, cleans output
  → execute_query()            # runs the native query and returns rows
```

Schema context (entities and attributes from the registry) is automatically injected into the prompt to ground the LLM.

```python
import anthropic
from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

client = anthropic.Anthropic()

def llm_fn(prompt: str) -> str:
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

registry = DataRegistry(
    store=MemoryJSONSource(),
    metadata_enricher=MetaData(llm_fn=llm_fn),
)
registry.sync_all(recursive=True)
registry.collect_source_stats("mydb", recursive=True)

rows = registry.execute_query_nl(
    "mydb",
    "show me all orders over $100",
    database="sales",
    collection="public",
)
```

Returns `[]` when no `llm_fn` is configured.

### Vector sources — embedding pipeline

For `VectorSource` backends (MemoryVectorSource, ChromaDBVectorSource, RedisVectorSource) **no LLM is needed**. The NL query is embedded into a vector and run as a KNN search:

```
NL query
  → embedding_fn(query)   # registry's embedding function produces a query vector
  → knn(index, vector)    # nearest neighbours by cosine similarity
  → rows
```

The registry automatically injects its `embedding_fn` when the target source is a VectorSource.

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

def embed(text: str) -> list[float]:
    ...  # your embedding function

vec_src = MemoryVectorSource("docs")
# ... create index and upsert docs with embeddings ...

registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=embed,
    vector_dim=1536,
)
registry.register_source(vec_src)

results = registry.execute_query_nl(
    "docs",
    "documents about machine learning",
    collection="docs",
    optional_properties={"k": 10},
)
```

Returns `[]` when no embedding function is configured on the registry.

---

### Tool-based NL2Q — multi-turn tool loop

`execute_query_nl_tools` drives a multi-turn LLM tool loop. Instead of packing the full schema into a single prompt, the LLM calls whichever tools it needs — exploring schema, sampling data, checking column statistics — then issues the final query.

**Source-level** (no registry required):

```python
def llm_fn(messages, tools, system=None):
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=tools,
        messages=messages,
        **({"system": system} if system else {}),
    )
    return {"stop_reason": resp.stop_reason, "content": [b.model_dump() for b in resp.content]}

rows = source.execute_query_nl_tools(
    query="which customers placed orders over $100?",
    database="sales",
    collection="public",
    llm_fn=llm_fn,
)
```

**Registry-level** (adds `get_enriched_metadata` — reads semantic types, descriptions, and value semantics stored by the enrichment pipeline):

```python
registry = DataRegistry(
    store=MemoryJSONSource(),
    metadata_enricher=MetaData(llm_fn=llm_fn_single_turn),
)
registry.sync_source("mydb", recursive=True)
registry.collect_source_stats("mydb", recursive=True)
registry.enrich_source_metadata("mydb", recursive=True)

rows = registry.execute_query_nl_tools(
    source="mydb",
    query="which customers placed orders over $100?",
    database="sales",
    collection="public",
)
```

The registry pulls its tool-loop LLM from `metadata_enricher._llm_fn`. Tools available in the loop:

| Tool | Returns |
|---|---|
| `list_databases` | Database names |
| `list_collections` | Collection / schema names |
| `get_schema` | Entities and attribute types |
| `get_sample` | Sample rows + row count |
| `get_column_stats` | Distinct count, min, max, null count, sample values |
| `get_relations` | Foreign key relationships |
| `execute_query` | Run native query, return rows |
| `get_enriched_metadata` | Registry enrichment metadata (registry path only) |

Graph sources replace `execute_query` with graph-native traversal tools (`match_nodes`, `get_node`, `get_neighbors`, `match_edges`). Tool definitions are overridable per dialect via `get_nl_tools()`.
