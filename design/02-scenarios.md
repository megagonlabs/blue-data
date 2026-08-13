# blue-data — Scenarios

## Scenario 1: Connecting and Syncing a SQL Database

A developer connects a SQLite database to the registry and discovers its full structure. The registry records the hierarchy — source → database → collection → entity → attribute — so any downstream tool can navigate it without touching the live database.

**Example:**

```python
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

registry = DataRegistry()
source = SQLiteDBSource(
    name="northwind",
    properties={"connection": {"database_directory": "/data/northwind"}}
)
registry.register_source(source)
registry.sync_source("northwind", recursive=True)
```

After sync, the registry holds records for every table and column in the Northwind database, addressable by path:

```
/source/northwind/database/northwind/collection/public/entity/orders
/source/northwind/database/northwind/collection/public/entity/orders/attribute/freight
```

Running sync a second time is a no-op if nothing has changed; new tables or dropped columns are reconciled automatically.

---

## Scenario 2: Collecting Statistics

A developer runs stats collection to populate each attribute record with row counts, distinct value counts, null counts, and sample values. Sample values are the input that drives all downstream enrichment — without them, Layer 1 and Layer 2 enrichment have no data to reason over.

**Example:**

```python
registry.collect_source_stats("northwind", recursive=True)

attr = registry.get_record(
    "/source/northwind/database/northwind/collection/public/entity/products/attribute/discontinued"
)
print(attr["properties"]["stats"])
# {"row_count": 77, "distinct_count": 2, "null_count": 0, "sample_values": [0, 1]}
```

Stats are stored as `record["properties"]["stats"]` and persist between sessions when a `RedisJSONSource` backend is used.

---

## Scenario 3: Detecting Coded Values (Layer 1 Enrichment)

A database uses opaque coded values — integer flags, short strings — that have semantic meaning not reflected in the schema. A query for "discontinued products" against a bare schema will produce `WHERE discontinued = 'discontinued'`, returning zero rows. Layer 1 enrichment detects ENUM-like columns from sample values alone, without any LLM, and writes the actual coded values to the attribute record.

**Example (Northwind):**

`products.discontinued` has sample values `[0, 1]` — two distinct integers covering every row. The inferencer classifies it as `BINARY_FLAG` and records the values.

An agent given this enriched record knows to write `WHERE discontinued = 1` rather than a string predicate.

**Example (Czech banking):**

`trans.type` has sample values `['PRIJEM', 'VYDAJ', 'UVER']`. The inferencer classifies it as `ENUM`. An agent given this record now knows the only valid values and writes `WHERE type = 'PRIJEM'` for credit transactions.

```python
registry.enrich_source("northwind")

attr = registry.get_record(
    "/source/northwind/.../entity/products/attribute/discontinued"
)
print(attr["properties"]["value_semantics"])
# {"semantic_type": "BINARY_FLAG", "sample_values": [0, 1], ...}
```

---

## Scenario 4: LLM-Augmented Enrichment (Layer 2)

A developer runs Layer 2 enrichment to generate natural-language descriptions for every entity and attribute. Descriptions are stored in the registry and indexed for vector search — so "shipping cost" can find `orders.freight` at search time with no LLM call.

**Example:**

```python
from blue_data.registry.enrichment.metadata import MetaData
import anthropic

client = anthropic.Anthropic()
registry = DataRegistry(
    metadata_enricher=MetaData(
        llm_fn=lambda prompt: client.messages.create(
            model="claude-opus-4-8", max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        ).content[0].text
    )
)

registry.sync_source("northwind", recursive=True)
registry.collect_source_stats("northwind", recursive=True)
registry.enrich_source_metadata("northwind", recursive=True)
```

After enrichment, `orders.freight` carries the description *"shipping cost charged for the order"*. A search for "shipping cost" now returns it with high vector similarity, even though no token in the query matches the column name.

Layer 2 enrichment is **incremental** — re-running it with `rebuild=False` (the default) preserves existing descriptions and only enriches attributes that have none yet.

---

## Scenario 5: Semantic Discovery via Hybrid Search

An agent or analyst needs to find the right table or column for a business concept without knowing the schema. The hybrid BM25 + vector search engine returns ranked results across all records in the registry — spanning all registered sources.

**Example:**

```python
results = registry.search_records("current account balance")
for r in results:
    print(r["path"], r["score"])
# /source/.../entity/account/attribute/balance     0.91
# /source/.../entity/loan/attribute/payments       0.74
# /source/.../entity/trans/attribute/balance       0.68
```

The search combines keyword (BM25) and vector (cosine similarity) scores. The `balance` attribute in the `trans` event-log table scores high and carries a process-semantics annotation indicating it is the most-recent-row value — so an agent knows to use `ORDER BY date DESC LIMIT 1` rather than `AVG(balance)`.

---

## Scenario 6: Multi-Source Registry

An enterprise has data spread across a SQLite warehouse, a Postgres analytics database, and a MongoDB document store. A single `DataRegistry` instance holds all three. Search and enrichment operate across all sources simultaneously, making cross-source relationships visible to agents.

**Example:**

```python
registry.register_source(sqlite_source)
registry.register_source(postgres_source)
registry.register_source(mongo_source)

registry.sync_source("sqlite",   recursive=True)
registry.sync_source("postgres", recursive=True)
registry.sync_source("mongo",    recursive=True)

registry.enrich_source_metadata("sqlite",   recursive=True)
registry.enrich_source_metadata("postgres", recursive=True)
registry.enrich_source_metadata("mongo",    recursive=True)

results = registry.search_records("customer orders")
# Returns ranked results from all three sources
```

Each source keeps its own record subtree under `/source/{name}/...`. The search engine indexes all records from all sources into the same `VectorSource` index.

---

## Scenario 7: Process and Temporal Reasoning

An event-log table stores one row per transaction over time. A naive query for "current account balance" computes `AVG(balance)` — averaging all historical records instead of reading the latest. Layer 1 enrichment detects EVENT tables from sample data patterns and annotates the entity record with process semantics: the event-time column, state variables, and the correct temporal operator.

**Example:**

The `trans` table in the Czech banking dataset has a `date` column with monotonically increasing values and a `balance` column whose values change per row. The inferencer detects:
- `trans` → entity type: `EVENT_LOG`
- `date` → role: `EVENT_TIME`
- `balance` → role: `STATE_VARIABLE`, operator: `LAST`

An agent given this enriched schema context now writes:

```sql
SELECT balance FROM trans
WHERE account_id = ?
ORDER BY date DESC LIMIT 1
```

instead of `SELECT AVG(balance) FROM trans WHERE account_id = ?`.

---

## Scenario 8: Platform Access via MCP

A developer connects Claude Desktop to the registry through the `registry-mcp` server. Claude can then search for data, inspect schemas, explore sources, and submit natural-language queries — all via the MCP tool interface, with no Python code required on the user side.

**Example:**

```json
{
  "mcpServers": {
    "blue-data": {
      "command": "blue-data-registry-mcp",
      "env": {
        "BLUE_DATA_REGISTRY_STORE": "redis",
        "BLUE_DATA_REGISTRY_REDIS_URL": "redis://localhost:6379/0",
        "BLUE_DATA_LLM_PROVIDER": "anthropic"
      }
    }
  }
}
```

Claude can then call:
- `search` — "find columns related to shipping cost"
- `explore` — "what databases are registered?"
- `inspect` — "show me the schema for the orders table"
- `query` — "how many discontinued products are in the northwind database?"

The MCP server is stateless per call; all state lives in the Redis-backed registry.
