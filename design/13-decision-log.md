# blue-data — Decision Log

Each entry records a significant design decision: what was decided, why, and what consequences follow.

---

## ADR-001 — Registry path convention `{scope}/{type}/{name}`

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** Every record is keyed by `{scope}/{type}/{name}`, where `scope` encodes the full ancestry path:

| Level | scope | type | Example key |
|-------|-------|------|-------------|
| Source | `/` | `source` | `/source/northwind` |
| Database | `/source/northwind` | `database` | `/source/northwind/database/northwind` |
| Collection | `/source/northwind/database/northwind` | `collection` | `/source/northwind/database/northwind/collection/public` |
| Entity | `/source/northwind/database/northwind/collection/public` | `entity` | `/source/northwind/database/northwind/collection/public/entity/orders` |
| Attribute | `…/entity/orders` | `attribute` | `…/entity/orders/attribute/order_date` |

The root key `$` holds top-level registry metadata.

**Rationale:** Listing all records of a type under a scope is a prefix scan — no secondary index needed. The path is self-describing: reading a key tells you exactly where in the hierarchy the record lives. Adding new levels (e.g. a "schema" level between database and collection) only requires a new `type` value — the convention itself does not change.

**Consequences:**
- Keys grow long for deep records (attribute keys can be 100+ characters).
- Renaming a source requires rewriting all descendant keys — there is no normalization.

---

## ADR-002 — The `rebuild` flag is three-state (`True` / `False` / `None`)

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** `rebuild` is a three-state flag on all registry write methods:

| Value | Meaning |
|-------|---------|
| `True` | Force re-index this record immediately, regardless of instance default |
| `False` | Suppress re-indexing for this write |
| `None` (default) | Defer to `DataRegistry._rebuild` instance-level default |

`DataRegistry._rebuild` is set at construction time and applies to all writes that pass `rebuild=None`.

**Rationale:** Bulk operations (sync, stats collection, enrichment) need to suppress per-record indexing and batch a single re-index at the end — O(n) instead of O(n²). One-off writes should index immediately. A simple boolean cannot express both behaviours without the caller knowing the instance policy. A simple boolean `True`/`False` was considered but rejected.

**Consequences:**
- Bulk callers pass `rebuild=False` to suppress per-record indexing, then trigger a single bulk re-index at the end.
- Tests set `DataRegistry(_rebuild=False)` globally and never pay embedding costs.
- Three states are less obvious than a boolean. Callers must understand that `None` is not the same as `False`.
- The instance-level default adds implicit state that can surprise callers who don't know what `_rebuild` is set to.

---

## ADR-003 — Three independent hierarchy ABCs (`DataSource`, `JSONSource`, `VectorSource`)

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** The three storage concerns are three separate ABCs with distinct contracts:
- `DataSource` — external data systems (SQL, NoSQL, files)
- `JSONSource` — registry state persistence (key-value); inherits `DataSource` for the lifecycle/property protocol only
- `VectorSource` — search index; inherits `DataSource` for the lifecycle/property protocol only

`JSONSource` and `VectorSource` share the `DataSource` lifecycle base but are not external data sources — they back the registry store and search index respectively.

**Rationale:** These hierarchies have fundamentally different contracts. Merging them into a single hierarchy would create an ABC with dozens of methods, most irrelevant to any given implementation. Separating them keeps each ABC minimal and lets concrete classes mix only the hierarchies they need.

**Consequences:**
- Callers must be aware of which hierarchy they are working with — a `RedisJSONSource` is not a `VectorSource` even though both touch Redis.
- `DataRegistry` composes all three: it owns a `JSONSource` for persistence, a `VectorSource` for search, and a dict of `DataSource` objects for live data.

---

## ADR-004 — `DataSource` methods default to no-op; subclasses override only what they support

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** `DataSource` base class provides no-op implementations of all interface methods. Subclasses override only the methods relevant to their source type. `execute_query` returns `[]` by default (no-op, not an error).

**Rationale:** Not all sources support all operations. A file-based source cannot `create_database`; a read-only source cannot run DDL. Forcing all subclasses to implement every method would produce dozens of `raise NotImplementedError` stubs across every implementation. Default no-ops are safer and produce cleaner subclasses.

**Consequences:**
- Callers cannot assume a method is supported just because it exists. Feature detection is at the instance level.
- The REST API's `connect_source` handler catches `Exception` broadly to tolerate sources that don't implement `fetch_databases` or `fetch_database_collections`.

---

## ADR-005 — Registry persistence is decoupled from the `DataRegistry` via `JSONSource` ABC

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** `DataRegistry` accepts a `JSONSource` at construction time. The registry itself does not know which backend (memory, file, Redis) is being used — it calls only `get(path)`, `set(path, value)`, `delete(path)`.

**Rationale:** Swapping backends should require only a constructor change. Tests use `MemoryJSONSource` (in-process, no I/O). Development uses `FileJSONSource` (persists to disk). Production uses `RedisJSONSource` (multi-process safe, durable). The registry code is unchanged in all three cases.

**Consequences:**
- Adding a new backend (e.g. MongoDB, S3) requires only a new `JSONSource` subclass — no changes to `Registry` or `DataRegistry`.
- `JSONSource` is the lowest-level abstraction in the stack. Everything in `blue-data` ultimately calls `JSONSource.get/set/delete`.

---

## ADR-006 — `sync_source` is idempotent and non-destructive

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** `sync_source(recursive=True)` walks the live `DataSource` and registers anything that does not yet exist in the registry. It never deletes registry records, even if the corresponding object no longer exists in the live source.

**Rationale:** Syncing should be safe to run repeatedly without risk of data loss. Registry records accumulate human-written enrichment (descriptions, metadata) that should not be destroyed because a table was temporarily dropped or a database was renamed. Deletion requires an explicit API call.

**Consequences:**
- Removed entities remain in the registry until explicitly deregistered via `DELETE` API. Stale records accumulate over time if not cleaned up.
- `sync_source` is always safe to call (idempotent, non-destructive). It is called at startup for every source in `BLUE_DATA_SOURCES_CONFIG`.

---

## ADR-007 — Stats and metadata stored as properties on registry records, not separate records

**Date:** 2024-Q4  
**Status:** Accepted

**Decision:** Statistical summaries (row counts, nulls, sample values) and semantic enrichment properties are stored directly on the existing registry record's `"properties"` dict. No separate record type is created. Stats are stored under the key `"stats"`; enrichment properties (`value_semantics`, `semantic_role`, `quantitative_vst`, etc.) are stored as top-level keys on `"properties"` — not nested under a `"metadata"` wrapper.

**Rationale:** A separate record type for stats would double the number of registry paths and require callers to join two records to get a complete picture of an attribute. Properties on the same record are simpler to read and write, and the `get_entity` MCP tool can return a fully enriched view in a single call.

**Consequences:**
- Enrichment and stats are overwritten in place — there is no history. `rebuild=True` clears and rewrites; `rebuild=False` preserves existing properties.
- The `"properties"` dict on a record can grow large for heavily-enriched attributes. The JSON size is bounded by the enrichment schema, not by data volume.

---

## ADR-008 — `MetaData` enrichment is layered: deterministic first, LLM optional

**Date:** 2025-Q1  
**Status:** Accepted

**Decision:** `enrich_source_metadata` runs in two layers:
1. **Deterministic** — semantic_role, quantitative VST classification, process_semantics, semantic_links. No API call. Always runs.
2. **LLM** — value_semantics inference, semantic_discovery, entity description generation. One call per attribute/entity. Runs only when `BLUE_DATA_LLM_PROVIDER` is set.

**Rationale:** Many enrichment decisions can be made deterministically from stats (e.g. a column with 100% numeric values and a "%" suffix is a quantitative measure). LLM calls are expensive and slow — restricting them to the cases where deterministic inference is insufficient keeps cost proportional to need. A deployment without an LLM API key still gets meaningful enrichment.

**Consequences:**
- `enrich_source` (deterministic semantic type inference) and `enrich_source_metadata` (full pipeline) are separate methods. `enrich_source` is a subset of `enrich_source_metadata` and can run standalone.
- The order matters: stats must be collected before any enrichment can run — both deterministic and LLM layers read from `attribute.properties["stats"]`.

---

## ADR-009 — Hybrid BM25 + vector search over registry records

**Date:** 2025-Q1  
**Status:** Accepted

**Decision:** `search_records` uses hybrid BM25 + vector scoring, not pure keyword or pure semantic search. BM25 matches on record name, type, description, and property keys; vector search matches on an embedding of the same text. Scores are combined with configurable weights.

**Rationale:** Registry records are short (a few hundred characters at most). Pure semantic search loses keyword precision for exact entity names (e.g. "OrderDate"); pure BM25 loses semantic reach (e.g. "revenue" should match a column named "total_due"). Hybrid search gives precision and recall.

**Consequences:**
- Vector search requires `VectorSource`. Without one (memory-only, no Redis), `search_records` falls back to BM25-only.
- Embedding dimension is fixed at construction time via `BLUE_DATA_REGISTRY_VECTOR_DIM`. Changing it requires dropping and recreating the search index.
- BM25 and vector weights are tunable via env vars without code changes — useful for domain-specific calibration.

---

## ADR-010 — Two MCP servers: Registry MCP and JSON MCP

**Date:** 2025-Q1  
**Status:** Accepted

**Decision:** Two separate MCP servers are provided. The Registry MCP exposes the full `DataRegistry` interface (search, sync, enrich, query). The JSON MCP exposes the raw `JSONSource` interface (get/set/delete/list_keys).

**Rationale:** The Registry MCP is the production interface — everything an LLM needs to discover, explore, and enrich data assets. The JSON MCP is a debugging tool that exposes the raw backing store without any registry abstraction. Mixing them into one server would expose dangerous low-level write operations (arbitrary key overwrite) alongside user-facing exploration tools.

**Consequences:**
- The JSON MCP is not intended for production use. It has no authorization checks — any caller with MCP access can overwrite arbitrary registry state.
- Both servers read from the same `JSONSource` — they can be connected to the same backing store simultaneously.

---

## ADR-011 — `BLUE_DATA_SOURCES_CONFIG` JSON file for startup source loading

**Date:** 2025-Q1  
**Status:** Accepted

**Decision:** Sources can be pre-loaded at startup from a JSON config file pointed to by `BLUE_DATA_SOURCES_CONFIG`. When the file is present, all sources in it are registered and optionally synced before the first request.

**Rationale:** Registering sources via the API or CLI on every deploy is error-prone and order-dependent. A declarative config file is idempotent and version-controllable. It is the primary deployment mechanism for environments where the source topology is known ahead of time.

**Consequences:**
- Dynamic source registration (via `POST /{source_name}` equivalent or CLI `source add`) still works and is the only option for sources added after deploy.
- `BLUE_DATA_SOURCES_SYNC=false` can be set to load sources without syncing — useful when the live source is slow to respond at startup.

---

## ADR-012 — `blue_data.utils.config`: profile-driven configuration for the CLI family

**Date:** 2026-09-15
**Status:** Accepted

**Decision:** Profile-driven configuration lives in `blue_data.utils.config`, shared by every Blue CLI rather than reimplemented per repository. A CLI declares its parameters in a JSON spec — each with a `default`, a `prompt`, whether it is `required`, an optional `inherits` chain, and a `cast` (`directory`, `file`, `str`, `int`, `float`, `bool`, `secret`) — and merges it with `base_spec()`, which holds the family-wide parameters (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `BLUE_DATA_LLM_PROVIDER`, `BLUE_DATA_LLM_MODEL`, `BLUE_DATA_CLI_FORMAT`, `BLUE_DATA_CLI_LOG_LIMIT`). Values are stored per CLI in `~/.<cli>/.profiles`, an INI file with one section per profile, mode `0600`; the selected profile is named in `~/.<cli>/.selected.profile`. Resolution order is **command option > environment variable > profile > spec default**. Secrets are stored either base64-encoded or as a `$VAR` reference resolved from the environment at use. `ConfigResolver.export()` writes the resolved values into `os.environ`. `ProfileStore.initialize()` gives a CLI a startup hook that creates the `default` profile on a fresh install, keyed on the profiles file rather than the section so an explicitly removed profile is not resurrected, and leaving the section empty so unset values keep tracking spec defaults.

**Rationale:** The CLI compliance checklist requires that `profile` behave consistently across repositories, which a copy-paste implementation would not survive. Putting the engine here makes the first implementation the shared one. The package deliberately imports no CLI framework, so `blue-data`'s dependencies (pandas, numpy, jsonpath-ng) are unchanged: it decides what to ask for and what a value resolves to, while prompting and command wiring stay in each CLI. Exporting into `os.environ` is what makes the rest work unchanged — a profile *is* a named set of environment variables, so everything that already reads configuration from the environment (the OpenAI SDK, this library's own `config.py`, Click's `envvar=` options) keeps doing so with no rewiring.

**Consequences:** A resolver reads from a snapshot of the environment taken at construction and writes to the live one, so it never observes its own exports — without that, every value the CLI exported would report back as having come from the environment and an `inspect` command could not attribute a value to the tier that really set it. The same property means a long-lived process building two resolvers gets consistent answers. Secret encoding is obfuscation, not encryption: it keeps a key off a screen and out of a careless `grep`, and the `0600` file mode plus the `$VAR` reference form are the real protections — the documentation says so rather than implying a guarantee the implementation does not provide. `base_spec.json` ships as package data, so a CLI consuming this needs no copy of the family parameters. `blue-data-kb-source`'s `kb profile` group is the reference implementation; siblings adopting it write only their own spec and a thin Click layer.
