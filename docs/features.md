# Features

## Unified data source interface

Consistent API across heterogeneous backends. Register once, query uniformly.

- **SQL** — SQLite, PostgreSQL, MySQL
- **Document** — MongoDB
- **Graph** — Neo4j

Consistent operations across all: list databases / collections / entities, execute queries, collect stats, introspect schema.

---

## Data registry

A live catalog that mirrors source structure as addressable, searchable records.

- **Hierarchical structure** — databases → collections → entities → attributes
- Each record carries description, properties, statistics, and enriched metadata
- Sync from live sources on demand — incremental or recursive
- Stats collection at every level: row counts, value distributions, sample data

---

## Semantic enrichment

Automatically infers meaning from data. No LLM required.

- **Semantic type inference** — detects dates, currencies, identifiers, categories, free text, and more
- **Attribute roles** — classifies each column by its functional role (identifier, time dimension, grouping attribute, measurement)
- **Value axes** — magnitude and ordinal ranges from distributions
- **Process semantics** — detects event tables, temporal cadence, trend direction
- **Quantitative rules** — total/component relationships, safe aggregation guidance, derived metric candidates
- **Semantic links** — statistically validated relationships between attributes

---

## LLM-augmented metadata

When paired with an LLM (Anthropic, OpenAI, or any provider), generates natural-language descriptions, domain concept mappings, and interpretive semantics.

---

## Hybrid search

BM25 keyword + vector similarity search over all registry records, with hierarchical score propagation.

---

## Natural language querying

Translates natural language questions into native queries via pluggable LLM functions. Supported dialects:

- SQL — SQLite, PostgreSQL, MySQL
- Cypher — Neo4j
- MongoDB filters
- Vector sources — MemoryVectorSource, ChromaDB, Redis, File

---

## Data import

Source-to-source data import across SQLite, Postgres, MySQL, and FileSource, with a registry-level wrapper and MCP tool.

---

## MCP server

Exposes registry operations as tools for Claude and other MCP clients, enabling AI agents to explore and query your data autonomously.

---

## REST API and CLI

Full platform layer for production deployments and scripting.
