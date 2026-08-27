# blue-data — Overview

## Objective

Enterprise AI applications fail when they query data without understanding it. An LLM given a schema full of opaque column names (`k_symbol`, `a2`–`a16`, `freight`) produces plausible-looking but semantically wrong queries. It writes `WHERE type = 'credit'` against a column that stores `PRIJEM`. It averages an event-log balance column instead of reading the latest row. It searches for "shipping cost" and finds nothing, because the column is called `freight`.

The root cause is not the prompt — it is the absence of a data intelligence layer between raw data and the AI.

blue-data is that layer. It sits between enterprise data sources and AI agents, making data understandable, discoverable, and query-ready without modifying the underlying databases or their schemas.

## What blue-data Does

- **Register** heterogeneous data sources (SQL databases, document stores, graph databases) under a unified catalog backed by a persistent `JSONSource`
- **Introspect** source structure — databases → collections → entities → attributes → relations — and persist it as addressable registry records
- **Collect statistics** from live sources (row counts, distinct values, sample values) and store them as record properties; sample values drive downstream enrichment
- **Enrich** the catalog with two layers of semantic intelligence:
  - **Layer 1 (deterministic)** — `SemanticTypeInferencer` detects ENUM columns, event-log tables, value axes, and coded values from sample data alone; no LLM required
  - **Layer 2 (LLM-augmented)** — `MetaData` pipeline generates natural-language descriptions for entities and attributes, semantic role annotations, process semantics, and value-axis signals; each enrichment is stored as a record property and survives re-runs unchanged
- **Profile data quality** from collected stats — per-attribute metrics (missing values, disguised sentinels, format violations, typos, representation fragmentation, outliers, repairability) and entity-level summaries (worst attribute, row error rates) stored as registry properties and available to agents before any query runs; no LLM required
- **Search** the catalog through a hybrid BM25 + vector engine; queries like "shipping cost" find `orders.freight`; "no longer sold" finds `products.discontinued`; "current account balance" finds the right event-log column with the correct temporal operator
- **Expose** the catalog through four thin platform interfaces: Python library, REST API (FastAPI), CLI (Click), and MCP servers (registry-mcp, json-mcp)

## Design Philosophy

**Three distinct hierarchies that compose** — `DataSource` (external data access), `JSONSource` (catalog persistence), and `VectorSource` (search indexing) are independent abstractions that `DataRegistry` coordinates. Conflating them would couple unrelated concerns: a source adapter should know nothing about the registry, and the search index should know nothing about individual source types.

**Enrichment is additive and idempotent** — syncing, collecting stats, and enriching the same source twice produces the same result. Each enrichment step writes to a specific named property on a record and does not touch other properties. The `rebuild` flag on write methods makes the idempotency contract explicit: `False` (default) preserves existing enrichments; `True` overwrites them.

**Platform interfaces are thin adapters** — no business logic belongs in the API, CLI, or MCP layers. Each interface is a translation layer that maps its transport's inputs to `DataRegistry` calls and its outputs back to the transport's format. This means any capability added to `DataRegistry` is immediately available to all four interfaces.

**Records are the canonical unit** — all metadata, statistics, and descriptions are stored as properties on registry records. There are no separate metadata tables or parallel stores. This makes the catalog self-describing: any tool with access to the registry can introspect it without additional schema knowledge.
