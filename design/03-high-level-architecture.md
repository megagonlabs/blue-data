# blue-data — High Level Architecture

## Diagram

```
                    External Interfaces

┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Python Lib  │  │ Registry MCP │  │  JSON MCP   │  │  REST API   │  │     CLI     │
└──────┬──────┘  └──────┬───────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       └────────────────┴─────────────────┴────────────────┴────────────────┘
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                    DataRegistry                                      │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                                  Registry                                    │   │
│  │                   (path-keyed record store backed by JSONSource)             │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────┐     ┌────────────────────────────────────────┐ │
│  │         Source Manager           │     │           Search Engine                │ │
│  │                                  │     │                                        │ │
│  │  ┌────────────────────────────┐  │     │  ┌────────────────────────────────┐   │ │
│  │  │       DataSource ABC       │  │     │  │        RegistrySearch          │   │ │
│  │  │  ┌──────┐  ┌──────────┐   │  │     │  │  ┌────────────┐ ┌───────────┐  │   │ │
│  │  │  │SQLite│  │ Postgres │   │  │     │  │  │HybridSearch│ │RecordIndex│  │   │ │
│  │  │  └──────┘  └──────────┘   │  │     │  │  │ ┌──────┐   │ └───────────┘  │   │ │
│  │  │  ┌──────┐  ┌──────────┐   │  │     │  │  │ │ BM25 │   │               │   │ │
│  │  │  │MySQL │  │   File   │   │  │     │  │  │ └──────┘   │               │   │ │
│  │  │  └──────┘  └──────────┘   │  │     │  │  │ ┌────────┐ │               │   │ │
│  │  │  ┌──────┐  ┌──────────┐   │  │     │  │  │ │ Vector │ │               │   │ │
│  │  │  │Neo4j │  │  Stream  │   │  │     │  │  │ └────────┘ │               │   │ │
│  │  │  └──────┘  └──────────┘   │  │     │  │  └────────────────────────────┘   │ │
│  │  │  ┌──────────────────────┐  │  │     │  └────────────────────────────────────┘ │
│  │  │  │  Bayesian Network    │  │  │     │                                        │ │
│  │  │  └──────────────────────┘  │  │     │                                        │ │
│  │  └────────────────────────────┘  │     │                                        │ │
│  └──────────────────────────────────┘     └────────────────────────────────────────┘ │
│                                                                                      │
│  ┌────────────────────────────┐                                                      │
│  │    Enrichment Pipeline     │                                                      │
│  │                            │                                                      │
│  │  ┌──────────────────────┐  │                                                      │
│  │  │ SemanticTypeInfer.   │  │                                                      │
│  │  │   (Layer 1 — det.)   │  │                                                      │
│  │  └──────────────────────┘  │                                                      │
│  │  ┌──────────────────────┐  │                                                      │
│  │  │   MetaData (LLM)     │  │                                                      │
│  │  │   (Layer 2 — opt.)   │  │                                                      │
│  │  └──────────────────────┘  │                                                      │
│  └────────────────────────────┘                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
              │                                   │
┌─────────────▼──────────────┐    ┌──────────────▼──────────────────────────────────┐
│       JSONSource            │    │                  VectorSource                    │
│  ┌──────┐ ┌──────┐ ┌─────┐ │    │       ┌──────────────┐  ┌──────────────────┐    │
│  │Memory│ │ File │ │Redis│ │    │       │MemoryVector  │  │  RedisVector     │    │
│  └──────┘ └──────┘ └─────┘ │    │       │   Source     │  │    Source        │    │
└────────────────────────────┘    │       └──────────────┘  └──────────────────┘    │
                                   └─────────────────────────────────────────────────┘
```

## Components

### External Interfaces

Five interface adapters sit in front of `DataRegistry` and delegate to it. They share no internal logic — each is a thin translation layer over the Python library.

**Python Library** — Native Python API (`DataRegistry` and related classes). Used to embed blue-data directly in Python applications and agentic pipelines.

**Registry MCP** — Exposes DataRegistry operations as MCP tools, enabling LLM agents (Claude Desktop, Claude Code, etc.) to discover, explore, and enrich data assets without writing code. Three tool groups: Explore, Inspect, Manage.

**JSON MCP** — Exposes raw JSONSource operations (`get`, `set`, `delete`, `list_keys`) as MCP tools. Intended for development and registry debugging — direct key-value access to the backing store without going through the DataRegistry abstraction.

**REST API** — HTTP/JSON interface (FastAPI, port 8000). Three routers: records (search, list), sources (CRUD, sync, stats, enrich), and hierarchy (CRUD at every level). No business logic in handlers.

**CLI** — Click command group (`blue-data`). Commands: `sources add/list/remove`, `sync`, `stats`, `enrich`, `metadata`, `search`, `inspect`, `query`.

---

### DataRegistry

The top-level coordinator. Extends `Registry` with:

- A dict of named live `DataSource` objects (the **Source Manager**)
- Sync and stats methods that walk `DataSource` structure and write registry records
- Enrichment methods that annotate records with semantic intelligence
- A `RegistrySearch` instance wired to both the registry and `VectorSource`

`DataRegistry` is the only component that knows about all three hierarchies simultaneously — it coordinates reads from `DataSource`, writes to `JSONSource` (via `Registry`), and indexing in `VectorSource` (via `RegistrySearch`).

---

### Registry

Path-keyed record store. All metadata, statistics, and descriptions are stored as properties on records keyed by `{scope}/{type}/{name}` (e.g., `/source/northwind/database/northwind/collection/public/entity/Orders`).

Fires internal hooks (`_on_record_changed`, `_on_record_deleted`) on every write. When `rebuild=True`, these hooks trigger `RecordIndexer` to update the vector search index. The `rebuild` flag is three-state: `True` (force index), `False` (suppress), `None` (defer to `DataRegistry._rebuild` instance default).

---

### Source Manager

Not a separate class — this is the responsibility of `DataRegistry`. It owns a dict of `DataSource` objects, provides `register_source` / `deregister_source` / `get_source`, and delegates sync and stats calls to the appropriate `DataSource` implementation.

---

### DataSource

Abstract base class for external data adapters. Exposes a uniform interface for listing databases, collections, entities, attributes, and relations, and for executing ad-hoc queries. Subclasses override only the methods their backend supports.

Sources are organized into families. `VectorSource` and `JSONSource` are also `DataSource` subclasses but serve dual roles — they back the search index and registry store respectively, and are shown separately in the diagram.

**SQL**

| Backend | Class | Status |
|---------|-------|--------|
| SQLite | `SQLiteDBSource` | Full |
| PostgreSQL | `PostgresDBSource` | Full |
| MySQL | `MySQLDBSource` | Full |

**File**

| Backend | Class | Status |
|---------|-------|--------|
| CSV / JSON / JSONL / Parquet | `FileSource` | Full |

**Graph**

| Backend | Class | Status |
|---------|-------|--------|
| In-memory / file-backed | `MemoryGraphSource` / `FileGraphSource` | Full |
| Neo4j | `NEO4JSource` | Full |

**Stream**

| Backend | Class | Status |
|---------|-------|--------|
| In-memory | `MemoryStreamSource` | Full |
| File | `FileStreamSource` | Full |
| Redis Streams | `RedisStreamSource` | Full |

**Network**

| Backend | Class | Status |
|---------|-------|--------|
| Bayesian network (pgmpy) | `BayesianNetworkSource` | Full |

**Document / JSON** (dual-role — also registry persistence backend)

| Backend | Class | Status |
|---------|-------|--------|
| In-memory | `MemoryJSONSource` | Full |
| File | `FileJSONSource` | Full |
| Redis Stack | `RedisJSONSource` | Full |
| MongoDB | `MongoDBSource` | Partial |

**Vector** (dual-role — also search index backend)

| Backend | Class | Status |
|---------|-------|--------|
| In-memory (numpy cosine) | `MemoryVectorSource` | Full |
| File-persisted | `FileVectorSource` | Full |
| ChromaDB | `ChromaDBVectorSource` | Full |
| Redis Stack (RediSearch KNN) | `RedisVectorSource` | Full |

---

### Search Engine

`RegistrySearch` orchestrates hybrid BM25 + vector scoring over all registry records. Holds two sub-components:

**HybridSearch** — Combines BM25 keyword scoring (over record name, type, description, property keys) with vector cosine similarity (over an embedding of the same text). Scores are weighted and thresholded before ranking. Falls back to BM25-only when no `VectorSource` is configured.

**RecordIndexer** — Keeps `VectorSource` in sync with registry writes. Upserts a record into the vector index on every `register_record` / `update_record` call (when `rebuild=True`) and deletes it on `delete_record`.

---

### Enrichment Pipeline

Two-layer enrichment applied to registry records after sync and stats collection.

**Layer 1 — Deterministic** (`enrich_source`): `SemanticTypeInferencer` reads `attribute.properties["stats"]["sample_values"]` and classifies each attribute as `ENUM_CATEGORY`, `INTEGER`, `FLOAT`, `DATE`, `DATETIME`, `EMAIL`, `UUID`, `FREE_TEXT`, etc. `MetaData` then adds entity-level signals: `EVENT` / `SEQUENCE_EVENT` / `ATOMIC_EVENT` process semantics; value axes; semantic links between attributes. No API call — always available.

**Layer 2 — LLM-augmented** (`enrich_source_metadata`): Runs Layer 1 first, then calls `MetaData` for LLM-dependent enrichments: natural-language entity and attribute descriptions, richer value semantics inference, and semantic discovery (related concepts, synonyms). Skipped when no `BLUE_DATA_LLM_PROVIDER` is set.

---

### JSONSource

Registry persistence backend. Exposes `get(path)`, `set(path, value)`, `delete(path)`, `list_keys(prefix)`. Three implementations:

| Backend | Class | Persistence | Notes |
|---------|-------|-------------|-------|
| Memory | `MemoryJSONSource` | No | Default; in-process dict |
| File | `FileJSONSource` | Yes | JSON file; survives restarts; no vector search |
| Redis | `RedisJSONSource` | Yes | Production; multi-process safe; requires Redis Stack |

---

### VectorSource

Search index for hybrid BM25 + vector search. Separate from `JSONSource` and `DataSource`. All operations dispatched via `execute_query(op, ...)`: `VECTOR.CREATE_INDEX`, `VECTOR.UPSERT`, `VECTOR.DELETE`, `VECTOR.KNN`.

| Backend | Class | Notes |
|---------|-------|-------|
| Memory | `MemoryVectorSource` | In-process numpy cosine; for dev/test |
| File | `FileVectorSource` | File-persisted vectors |
| ChromaDB | `ChromaDBVectorSource` | ChromaDB backend |
| Redis | `RedisVectorSource` | RediSearch KNN; requires Redis Stack |
