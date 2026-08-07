# DataSource Hierarchy Mapping

Every `DataSource` exposes data through a five-level hierarchy:

```
source → database → collection → entity → attribute
```

This document records how each adapter maps its native concepts onto that hierarchy.

---

## Mapping table

| Source | database | collection | entity | attribute |
|---|---|---|---|---|
| **SQLiteDBSource** | `.db` file (without extension) | always `"public"` | table | column |
| **PostgresDBSource** | Postgres database | schema (e.g. `public`, `analytics`) | table | column |
| **MySQLDBSource** | MySQL database | always `"public"` | table | column |
| **MongoDBJSONSource** | MongoDB database | MongoDB collection | inferred document shape (sampled) | document field |
| **RedisJSONSource** | scan-prefix namespace | key-group (first segment after prefix) | inferred JSON document shape (sampled) | JSON field |
| **Neo4jGraphSource** | Neo4j database (e.g. `neo4j`) | same as database | node label | node property |
| **FileSource** | always `"default"` | file stem (e.g. `orders` for `orders.csv`) | same as collection | column / JSON field |
| **MemoryGraphSource** | named graph | same as database | node label | node property |
| **FileGraphSource** | named graph (persisted as `<name>.json`) | same as database | node label | node property |
| **MemoryVectorSource** | collection name | collection name | — | metadata field on vector doc |
| **FileVectorSource** | always `"default"` | collection name (persisted as `<name>.json`) | — | metadata field on vector doc |
| **ChromaDBVectorSource** | always `"default"` | ChromaDB collection | — | metadata field on vector doc |
| **RedisVectorSource** | scan-prefix namespace | index collection | — | metadata field on vector doc |
| **MemoryStreamSource** | stream name | stream name | — | message field |
| **FileStreamSource** | stream name | stream name (persisted as `<name>.jsonl`) | — | message field |
| **RedisStreamSource** | Redis stream key | Redis stream key | — | message field |
| **BayesianNetworkSource** | network name | network name | node (random variable) | state / value |

---

## Notes by source

### SQLiteDBSource

SQLite has no schema (namespace) concept. Every database is a single flat table space, so `collection` is always the string `"public"` — a placeholder that keeps the registry hierarchy consistent without adding a real schema layer.

### PostgresDBSource

Postgres schemas map naturally to `collection`. A single Postgres server can host multiple databases, each with multiple schemas. The typical default is `database=mydb / collection=public`.

### MySQLDBSource

MySQL conflates "database" and "schema" — there is no schema layer within a database. `collection` is fixed to `"public"` for the same reason as SQLite.

### MongoDBJSONSource

MongoDB collections have no fixed schema. `entity` and `attribute` are inferred by sampling documents and inspecting their field shapes. The schema is approximate and can diverge from actual data if documents are heterogeneous.

### RedisJSONSource

Redis has no native hierarchy. The mapping is imposed via key naming conventions:

- `database` is the `scan_prefix` (e.g. `registry`, `platform:data`)
- `collection` is the first segment of the key after the prefix (e.g. `registry:source:*` → collection `source`)
- `entity` and `attribute` are inferred by sampling JSON documents stored at matching keys

### Neo4jGraphSource

Neo4j organises data as a property graph, not as tables. The mapping is:

- `entity` = node label (e.g. `Person`, `Product`)
- `attribute` = node property (e.g. `name`, `age`)
- Relations between node labels are registered as `relation` records, not entities

`collection` is the same string as `database` because Neo4j has no concept below the database level that corresponds to a schema or collection.

### FileSource

Each file in the configured directory is one `collection`. The entity name equals the collection name (one entity per file). `attribute` is inferred from the file's columns or top-level JSON keys.

Supported formats: CSV, JSON (array of records), JSONL, Parquet.

### Graph sources (Memory / File)

Both share the same mapping. `MemoryGraphSource` holds everything in-process; `FileGraphSource` persists each database as a `<name>.json` sidecar file. Neither has a meaningful `collection` distinction below the database level — `fetch_database_collections` returns the database name itself.

### Vector sources (Memory / File / ChromaDB / Redis)

Vector sources are indexing backends, not structured data stores. They do not have an `entity` → `attribute` concept in the relational sense. Metadata fields attached to vector documents (e.g. `name`, `type`, `scope`) surface as attributes for introspection purposes, but there are no rows or columns.

### Stream sources (Memory / File / Redis)

Streams are append-only event logs. Each stream maps to both `database` and `collection` (they are the same thing at the stream level). Individual message fields can surface as attributes during schema introspection, but streams are not queried like tables.

---

## Design invariants

**`collection` is never empty.** Sources that have no native schema/namespace concept (SQLite, MySQL, graph sources) return a synthetic collection name — either `"public"` or the database name itself — so that the registry path always has four levels below `source`.

**`entity` and `attribute` are always derived, never user-defined.** They are populated by `fetch_database_collection_entities` / `fetch_database_collection_relations` from the live source and reconciled into the registry by `sync_source`. User-defined metadata (descriptions, tags) is layered on top via `properties`.

**Vector and stream sources do not fully implement the hierarchy.** `entity` and `attribute` are vestigial for these source types. `fetch_database_collection_entities` returns an empty dict for most vector and stream sources. This is by design — the registry records that matter for these sources are at the `collection` level and above.
