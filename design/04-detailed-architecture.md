# blue-data — Detailed Architecture

## External Interfaces

All five interfaces are thin adapters over the Python library. Each delegates to `DataRegistry`.

| Interface | Technology | Primary Use |
|-----------|-----------|-------------|
| Python Library | Native Python API | Embedding blue-data directly in Python applications and pipelines |
| Registry MCP | fastmcp, stdio | LLM agent tool use (Claude Desktop, Claude Code, etc.) |
| JSON MCP | fastmcp, stdio | Development and registry debugging — raw JSONSource access |
| REST API | FastAPI, port 8000 | Non-Python consumers and microservice deployments |
| CLI | Click (`blue-data`) | Development, administration, scripting |

---

## Information Flow

### Registration Path

1. Caller constructs a `DataSource` (e.g. `SQLiteDBSource`) and calls `registry.register_source(source)`
2. `DataRegistry` adds the source to `self.sources[name]` and calls `Registry.register_record` to create the top-level source record at path `/source/{name}`
3. The source record carries the source type and connection properties; no live connection is made at registration time

---

### Sync Path (`sync_source`)

1. Caller calls `registry.sync_source(name, recursive=True)`
2. `DataRegistry` calls `source.fetch_databases()` — the live `DataSource` queries its backend
3. For each database: `register_record` / `update_record` at `/source/{n}/database/{db}` (with `rebuild=False` to suppress per-record indexing during bulk sync)
4. With `recursive=True`: for each database → `source.fetch_database_collections(db)` → for each collection → `source.fetch_database_collection_entities(db, col)` → for each entity → `source.fetch_database_collection_entity_attributes(db, col, entity)` → for each relation → register/update records at each level
5. After all records are written, a single bulk re-index is triggered on `RegistrySearch`

Sync is **idempotent** — calling it twice on an unchanged source produces no diff. It never deletes records, even if the corresponding database object no longer exists in the live source.

---

### Stats Path (`collect_source_stats`)

1. Caller calls `registry.collect_source_stats(name, recursive=True)`
2. For each registered entity attribute, `DataRegistry` calls `source.fetch_database_collection_entity_attribute_stats(db, col, entity, attr)` on the live source
3. The result (`count`, `distinct_count`, `null_count`, `sample_values`, `min`, `max`) is written to `attribute_record["properties"]["stats"]` via `Registry.update_record` (with `rebuild=False`)
4. Entity-level stats (`row_count`) and collection-level stats (`num_entities`) are written similarly
5. `sample_values` is the primary input for Layer 1 enrichment — stats must be collected before `enrich_source` is called

---

### Enrichment Path — Layer 1 (`enrich_source`)

1. Caller calls `registry.enrich_source(name)`
2. For each attribute record with a `stats.sample_values` property, `SemanticTypeInferencer.infer(sample_values)` classifies the attribute
3. Detected properties written to `attribute_record["properties"]`:
   - `value_semantics.semantic_type` — `ENUM`, `BINARY_FLAG`, `NUMERIC_ID`, `CONTINUOUS`, `DATE`, `FREE_TEXT`, `UUID`, etc.
4. Entity-level signals are also detected from attribute patterns:
   - `process_semantics` — `EVENT_LOG`, `SNAPSHOT`, `REFERENCE`
   - `semantic_links` — foreign-key and natural join candidates
   - `value_axis` — presence of a natural temporal or ordinal axis
5. All writes use `rebuild=False`; a single re-index fires at the end

No API calls — Layer 1 runs entirely from sample data.

---

### Enrichment Path — Layer 2 (`enrich_source_metadata`)

1. Caller calls `registry.enrich_source_metadata(name, recursive=True, rebuild=False)`
2. `DataRegistry` calls `enrich_source(name)` first (Layer 1 runs unconditionally)
3. `MetaData.collect_source_metadata(registry, source_name, rebuild)` is called for LLM-dependent enrichments
4. For each attribute (unless `rebuild=False` and the property already exists):
   - `enrich_attribute_vsi(attr_record)` — constructs a prompt from name, type, sample values, and stats; calls `llm_fn`; writes richer `value_semantics` inference back to the record
   - `infer_attribute_sdi(attr_record)` — discovers related concepts, synonyms, and usage patterns via `llm_fn`; writes `semantic_discovery`
   - `semantic_role` and `quantitative_vst` — set deterministically from Layer 1 signals without an LLM call
5. For each entity (unless `rebuild=False` and `description` already exists):
   - `enrich_entity(entity_record, attr_records)` — constructs a prompt from entity name, attribute names, and sample stats; calls `llm_fn`; writes a natural-language `description` to the entity record
6. All writes use `rebuild=False`; a single re-index fires at the end

When no `metadata_enricher` is set (i.e. `BLUE_DATA_LLM_PROVIDER` is unset), steps 4–5 LLM calls are silently skipped — only Layer 1 properties are written.

---

### Search Path (`search_records`)

1. Caller calls `registry.search_records(query, type=None, scope=None, page_size=10)`
2. `DataRegistry` delegates to `RegistrySearch.hybrid_search(query, ...)`
3. **BM25 pass** — each record's text representation (name + description + property keys) is scored against the query terms using BM25
4. **Vector pass** — the query is embedded into a float vector; `VectorSource.VECTOR.KNN` returns the nearest records; cosine similarity scores are computed
5. Scores are combined: `score = bm25_weight * bm25_score + vector_weight * vector_score + value_weight * value_score`
6. Records below configured thresholds are discarded
7. Remaining records are ranked by combined score and the top-`page_size` slice is returned

When no `VectorSource` is configured (or vector scoring produces no results), the BM25 pass alone determines ranking.

---

### Query Execution Path

1. Caller calls `registry.execute_query(source_name, query, database=..., collection=...)`
2. `DataRegistry` retrieves the live `DataSource` from `self.sources[source_name]`
3. `DataSource.execute_query(database, query)` runs the native query against the backend
4. Rows are returned as `list[dict]`; no transformation or type coercion

For SQL sources, `query` is a SQL SELECT string. The result always returns rows as Python dicts regardless of backend type.

---

### Import Path (`import_data`)

1. Caller calls `registry.import_data(source, target, collection, database, entity, mode)`
2. `DataRegistry` retrieves both live `DataSource` objects
3. Reads rows from source via `source.execute_query` or `source.fetch_database_collection_entities`
4. Writes rows to target via `target.execute_query` (using INSERT or UPSERT SQL for SQL targets)
5. `mode="overwrite"` truncates the target entity before writing; `mode="append"` adds rows

---

## Component Contracts

### `DataSource`

```python
class DataSource(ABC):
    name: str
    properties: dict

    def fetch_databases(self) -> list[str]: ...
    def fetch_database_collections(self, database: str) -> list[str]: ...
    def fetch_database_collection_entities(self, database: str, collection: str) -> dict[str, DataSchema]: ...
    def fetch_database_collection_entity_attributes(self, database: str, collection: str, entity: str) -> list[dict]: ...
    def fetch_database_collection_relations(self, database: str, collection: str) -> list[dict]: ...
    def execute_query(self, database: str, query: str, optional_properties: dict | None = None) -> list[dict]: ...
    def fetch_database_collection_entity_attribute_stats(self, ...) -> dict: ...
```

Subclasses override only the methods they support. The base class raises `NotImplementedError` for all methods.

---

### `Registry`

```python
class Registry:
    def register_record(self, path: str, record: dict, rebuild: bool | None = None) -> None: ...
    def update_record(self, path: str, updates: dict, rebuild: bool | None = None) -> None: ...
    def get_record(self, path: str) -> dict | None: ...
    def delete_record(self, path: str, rebuild: bool | None = None) -> None: ...
    def list_records(self, prefix: str | None = None) -> list[dict]: ...
    def load(self, data: dict) -> None: ...
    def dump(self) -> dict: ...
```

Every record has the standard shape: `{name, type, scope, description, created_by, icon, properties, contents}`. `properties` is the open-ended dict where stats, enrichment results, and semantic annotations are stored.

---

### `JSONSource`

```python
class JSONSource(ABC):
    def get(self, path: str | None) -> Any: ...
    def set(self, path: str, value: Any) -> None: ...
    def delete(self, path: str) -> None: ...
    def list_keys(self, prefix: str | None = None) -> list[str]: ...
```

`path=None` or `path="$"` reads the root document. `delete(path)` removes the value at `path` and all descendant keys with that prefix.

---

### `VectorSource`

```python
class VectorSource(ABC):
    def execute_query(self, op: str, **kwargs) -> Any: ...
    # VECTOR.CREATE_INDEX  — collection: str, dim: int
    # VECTOR.UPSERT        — collection: str, id: str, vector: list[float], metadata: dict
    # VECTOR.DELETE        — collection: str, id: str
    # VECTOR.KNN           — collection: str, query_vector: list[float], k: int → list[dict]
```

---

### Record index lifecycle

```
register_source(src)
  └─ Registry.register_record(path, record, rebuild=True)
        └─ JSONSource.set(path, record)
        └─ _on_record_changed(path, record)
              └─ RecordIndexer.upsert(path, record)
                    └─ EmbeddingModel.embed(record_text) → vector
                    └─ VectorSource.VECTOR.UPSERT(id=path, vector=vector)

delete_record(path)
  └─ JSONSource.delete(path)
  └─ _on_record_deleted(path)
        └─ RecordIndexer.delete(path)
              └─ VectorSource.VECTOR.DELETE(id=path)
```

---

## Dependency Graph

```
blue-data (core library)
    ├── pandas              (DataSchema, stats)
    ├── numpy               (MemoryVectorSource cosine)
    └── jsonpath-ng         (JSONSource path queries)

Platform services
    ├── platform/api/       FastAPI + Uvicorn (REST API, port 8000)
    ├── platform/registry-mcp/  fastmcp (Registry MCP server)
    ├── platform/json-mcp/      fastmcp (JSON MCP server)
    └── platform/cli/       Click (CLI, blue-data command)

Optional backends (deferred imports in config.py)
    ├── redis[hiredis]      RedisJSONSource + RedisVectorSource
    ├── anthropic           MetaData LLM enrichment (claude-opus-4-8 default)
    └── openai              MetaData LLM enrichment (gpt-4o default)
```

---

## Three-Hierarchy Composition

`DataRegistry` is the only class that touches all three hierarchies:

```
DataSource  ──── reads live data (sync, stats, query)
     │
     │  sync_source writes records ──────────────────────────┐
     │                                                        ▼
     │                                                   JSONSource
     │                                               (registry persistence)
     │                                                        │
     │  search_records reads records ◄────────────────────────┘
     │                 embeds text ──────────────────────────┐
     │                                                        ▼
     │                                                   VectorSource
     │                                                 (search index)
     └──────────────────────────────────────────────────────────────────►
                                                         DataRegistry
                                                        (coordinates all)
```

The three hierarchies are intentionally independent ABCs. A `RedisJSONSource` and a `RedisVectorSource` both touch Redis but share no base class — they serve different contracts and are configured and used completely separately.
