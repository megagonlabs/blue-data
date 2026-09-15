# Quick Start

## Install

```bash
pip install -e lib/
```

Runtime dependencies (`pandas`, `numpy`) are installed automatically. No build step required.

---

## Five-step workflow

### 1. Register a source

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry()

source = SQLiteDBSource(
    name="mydb",
    properties={"connection": {"database_directory": "/tmp/my-data"}},
)
registry.register_source(source)
```

### 2. Sync the source structure

Walk the live source and mirror its hierarchy into the registry:

```python
registry.sync_source("mydb", recursive=True)
```

```python
registry.list_source_databases("mydb")
# → ['northwind']

registry.list_database_collections("mydb", "northwind")
# → ['public']

registry.list_collection_entities("mydb", "northwind", "public")
# → ['customers', 'orders', 'products', ...]
```

### 3. Collect statistics

Pull row counts, sample values, distinct counts, and min/max from the live source:

```python
registry.collect_source_stats("mydb", recursive=True)
```

Sample values drive all downstream enrichment — this step is required before enrichment or data quality profiling.

### 4. Enrich

**Deterministic enrichment** (no API key required):

```python
registry.enrich_source("mydb")
```

Detects ENUM columns, event-log tables, event-time columns, value axes, and coded domain values from sample data alone.

**LLM-augmented enrichment** (Anthropic or OpenAI):

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def llm_fn(prompt: str) -> str:
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

from blue_data.registry.enrichment.metadata import MetaData

registry = DataRegistry(
    metadata_enricher=MetaData(llm_fn=llm_fn),
)
registry.register_source(source)
registry.sync_source("mydb", recursive=True)
registry.collect_source_stats("mydb", recursive=True)
registry.enrich_source_metadata("mydb", recursive=True)
```

Generates natural-language descriptions for every entity and attribute, semantic role annotations, process semantics, and value-axis signals. Results are stored once in the registry and reused without further API calls.

### 5. Search

Keyword search over all registry records:

```python
results = registry.search_records("customer revenue monthly")
for r in results:
    print(r["name"], r["type"], r.get("_score"))
```

Add a `VectorSource` and `embedding_fn` for hybrid BM25 + vector search — "shipping cost" finds `orders.freight`, "current inventory" finds `products.units_in_stock`.

```python
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

def embed(text: str) -> list[float]:
    ...  # your embedding function (OpenAI, sentence-transformers, etc.)

registry = DataRegistry(
    vector_source=MemoryVectorSource(),
    embedding_fn=embed,
    vector_dim=1536,
)
```

---

## Natural language queries

Once enriched, issue plain-English queries against a registered source:

```python
rows = registry.execute_query_nl(
    "mydb",
    "show me all orders over $100",
    database="northwind",
    collection="public",
)
```

Requires `llm_fn` to be wired via `MetaData`. Returns `[]` when no LLM is configured.

---

## What's next

- **[Developer guide](guide.md)** — syncing, stats, enrichment, data quality profiling, search, and NL queries in depth
- **[Features](features.md)** — full feature list with descriptions and examples
- **[Configuration](../README.md#configuration)** — environment variables for storage backends, LLM providers, and search tuning
- **[Examples](../examples/README.md)** — runnable scenario and feature demos
