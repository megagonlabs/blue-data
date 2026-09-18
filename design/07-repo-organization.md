# blue-data — Repo Organization

## Directory Tree

```
blue-data/
│
├── .gitignore                           # ignored files (venvs, __pycache__, .env, build artifacts)
├── example.envrc                        # environment variable template — copy to .envrc and fill in values
├── README.md                            # project overview, quick start, platform table
│
├── data/                                # demo datasets (Northwind, Czech banking/finance, BIRD)
│   ├── bird/                            # BIRD benchmark: discovery queries + entity mappings (11 DBs); .sqlite files are gitignored — download separately
│
├── design/                              # design documents and ADRs
│   ├── 01-overview.md                   # objective, what blue-data does, design philosophy
│   ├── 02-scenarios.md                  # motivating scenarios that drive design decisions
│   ├── 03-high-level-architecture.md    # component map and data flow overview
│   ├── 04-detailed-architecture.md      # per-component design
│   ├── 05-software-stack.md             # language, frameworks, runtime dependencies
│   ├── 06-library.md                    # library package structure and import conventions
│   ├── 07-repo-organization.md          # directory layout, naming, and module boundaries
│   ├── 08-coding-style.md               # linting, typing, naming, and testing conventions
│   ├── 09-api-interface-spec.md         # REST API contract and OpenAPI alignment
│   ├── 10-data-model.md                 # registry record schema and JSONSource path conventions
│   ├── 11-testing-strategy.md           # unit vs integration tests, fixture policy, coverage
│   ├── 12-deployment-ops.md             # container, Redis Stack, and secrets configuration
│   ├── 13-decision-log.md               # Architectural Decision Records (ADRs)
│   └── design-process.md               # how to read and update the design documents
│
├── docs/                                # user-facing documentation
│   ├── README.md                        # docs index
│   ├── quickstart.md                    # five-step workflow: install, sync, stats, enrich, search
│   ├── guide.md                         # developer guide: syncing, enrichment, DQ profiling, search, NL queries
│   ├── features.md                      # feature-by-feature documentation with code examples
│   ├── installation.md                  # install instructions and extras
│   ├── architecture.md                  # three-hierarchy design explanation
│   ├── api-reference.md                 # full REST API reference
│   ├── datasource-hierarchy-mapping.md  # source → database → collection → entity → attribute path convention
│   ├── extending.md                     # adding a new DataSource backend
│   ├── mcp.md                           # MCP overview — which server to use and when
│   ├── api.md                           # stub → see platform/api/README.md
│   ├── cli.md                           # stub → see platform/cli/README.md
│   ├── json-mcp.md                      # stub → see platform/json-mcp/README.md
│   └── registry-mcp.md                  # stub → see platform/registry-mcp/README.md
│
├── examples/                            # runnable demos
│   ├── README.md
│   ├── claude_desktop_walkthrough.md    # step-by-step walkthrough via Claude Desktop
│   ├── backends/
│   │   ├── redis_demo.py                # RedisJSONSource + RedisVectorSource as persistent store
│   │   ├── registry_memory_example.py   # MemoryJSONSource + MemoryVectorSource, offline
│   │   ├── sqlite_data_registry_demo.py # DataRegistry with SQLiteDBSource
│   │   └── sqlite_example.py            # bare SQLiteDBSource usage
│   ├── benchmarks/                      # placeholder directory (benchmark scripts live in lib/tests/benchmarks/)
│   ├── feature-demos/
│   │   ├── data_quality_demo.py         # four-tier data quality profiling pipeline
│   │   ├── enrichment_demo.py           # MetaData: value semantics, semantic roles
│   │   ├── export_data_demo.py          # DataSource.import_data / export flow
│   │   ├── import_data_demo.py          # import_data from one source into another
│   │   ├── nl_query_demo.py             # execute_query_nl: NL → native query via LLM
│   │   ├── nl_tools_demo.py             # execute_query_nl_tools: agentic tool loop
│   │   ├── nl_tools_graph_demo.py       # tool loop over a graph source
│   │   └── schema_creation_demo.py      # DataSchema: add_entity / add_relation / to_str
│   ├── framework-demos/
│   │   ├── langgraph_api_demo.py        # LangGraph agent over the REST API
│   │   ├── langgraph_direct_demo.py     # LangGraph agent directly against DataRegistry
│   │   └── langgraph_mcp_demo.py        # LangGraph agent using MCP tools
│   ├── integration-demos/
│   │   └── sql_semantic_enrichment_demo.py  # sync SQLite source, enrich schema, NL2SQL
│   └── scenario-demos/
│       ├── coded_value_demo.py          # coded-value column semantics (ENUM / FLAG)
│       ├── data_quality_demo.py         # four-tier data quality profiling pipeline
│       ├── description_search_demo.py   # hybrid search across enriched registry records
│       └── process_reasoning_demo.py    # process semantics: EVENT, AGGREGATE_OVER_TIME
│
├── lib/                                 # Python library (blue-data PyPI package)
│   ├── README.md                        # library quick start and source layout
│   ├── pyproject.toml                   # package metadata, dependencies, extras, tool config
│   ├── src/
│   │   └── blue_data/
│   │       ├── __init__.py              # re-exports DataSource, VectorSource, JSONSource, DataRegistry, DataSchema
│   │       ├── config.py                # env-var configuration helpers
│   │       ├── core/
│   │       │   ├── schema.py            # DataSchema — in-memory entity/relation graph used for schema introspection
│   │       │   └── utils/
│   │       │       ├── json_utils.py    # JSON serialization helpers
│   │       │       ├── similarity_utils.py  # cosine similarity, numpy vector ops
│   │       │       └── utils.py         # deep_merge, safe_json_parse, path utilities
│   │       ├── utils/
│   │       │   └── config/              # Profile-driven configuration shared by the Blue CLI family
│   │       │       ├── spec.py          # ParamSpec/ConfigSpec — declared parameters and their casts
│   │       │       ├── profiles.py      # ProfileStore — the ~/.<cli>/.profiles file and the selected profile
│   │       │       ├── resolve.py       # ConfigResolver — precedence, $VAR references, export to os.environ
│   │       │       ├── secrets.py       # encode/decode/display of secret values
│   │       │       └── base_spec.json   # Family-wide parameters (OPENAI_API_KEY, BLUE_DATA_LLM_MODEL, …)
│   │       ├── registry/
│   │       │   ├── registry.py          # Registry — generic key/value record store over JSONSource
│   │       │   ├── data_registry.py     # DataRegistry — Registry + typed source helpers + search engine
│   │       │   ├── enrichment/
│   │       │   │   ├── description_generation.py  # LLM-based record description generation
│   │       │   │   ├── metadata.py      # MetaData — full attribute/entity enrichment pipeline
│   │       │   │   ├── metadata_utils.py # statistical utilities used by enrichment (pearson, temporal alignment, etc.)
│   │       │   │   ├── prompts.py       # LLM prompt templates for enrichment
│   │       │   │   ├── semantic_types.py # SemanticTypeInferencer — column type inference (deterministic)
│   │       │   │   └── utils.py         # enrichment utility functions
│   │       │   └── search/
│   │       │       ├── hybrid_search.py     # HybridSearch — BM25 + vector score fusion
│   │       │       ├── indexing.py          # RecordIndexer — keeps VectorSource in sync with registry writes
│   │       │       ├── keyword_search.py    # BM25 keyword search over registry record text
│   │       │       ├── ranking.py           # score fusion and result ranking
│   │       │       ├── registry_search.py   # RegistrySearch — wires HybridSearch + RecordIndexer for DataRegistry
│   │       │       ├── search_engine.py     # SearchEngine — top-level entry point with configurable weights
│   │       │       └── vector_search.py     # VectorSearch — KNN over indexed record embeddings
│   │       └── source/
│   │           ├── source.py                # DataSource — base ABC; fetch_*/create_*/execute_query interface
│   │           ├── file/
│   │           │   └── file_source.py       # FileSource — CSV/JSON file I/O
│   │           ├── graph/
│   │           │   ├── graph_source.py      # GraphSource ABC — node/edge interface
│   │           │   ├── memory_graph_source.py  # in-memory graph; dev/test
│   │           │   ├── file_graph_source.py    # file-persisted graph (JSON)
│   │           │   └── neo4j/
│   │           │       └── neo4j_graph_source.py  # Neo4j driver adapter
│   │           ├── json/
│   │           │   ├── json_source.py       # JSONSource ABC — get/set/delete interface; execute_query op dispatch
│   │           │   ├── memory_json_source.py   # in-memory dict; default Registry store
│   │           │   ├── file_json_source.py     # atomic file-backed JSON store
│   │           │   ├── mongodb/
│   │           │   │   └── mongodb_json_source.py
│   │           │   └── redis/
│   │           │       └── redis_json_source.py  # RedisJSON (Redis Stack) production store
│   │           ├── network/
│   │           │   └── bn/
│   │           │       ├── bayesian_network_source.py  # BayesianNetworkSource — pgmpy adapter
│   │           │       └── bn_utils.py
│   │           ├── sql/
│   │           │   ├── sql_source.py        # SQLSource ABC
│   │           │   ├── sqlite/
│   │           │   │   └── sqlite_sql_source.py  # fully implemented; db files in configurable dir
│   │           │   ├── mysql/
│   │           │   │   └── mysql_sql_source.py
│   │           │   └── postgres/
│   │           │       └── postgres_sql_source.py
│   │           ├── stream/
│   │           │   ├── stream_source.py     # StreamSource ABC
│   │           │   ├── memory_stream_source.py
│   │           │   ├── file_stream_source.py
│   │           │   └── redis/
│   │           │       └── redis_stream_source.py  # Redis Streams
│   │           └── vector/
│   │               ├── vector_source.py     # VectorSource ABC — create_index/upsert/delete/knn + execute_query dispatch
│   │               ├── memory_vector_source.py  # in-memory numpy cosine; dev/test; no Redis
│   │               ├── file_vector_source.py    # file-persisted vectors
│   │               ├── chromadb/
│   │               │   └── chromadb_vector_source.py
│   │               └── redis/
│   │                   └── redis_vector_source.py  # RedisSearch KNN (Redis Stack)
│   └── tests/
│       ├── unit/                            # per-module tests; all external services mocked
│       │   ├── test_bayesian_network_source.py
│       │   ├── test_chromadb_vector_source.py
│       │   ├── test_data_registry_unit.py
│       │   ├── test_datasource_lifecycle.py
│       │   ├── test_execute_query_nl.py
│       │   ├── test_export_data.py
│       │   ├── test_file_graph_source.py
│       │   ├── test_file_json_source.py
│       │   ├── test_file_source.py
│       │   ├── test_graph_execute_query.py
│       │   ├── test_graph_source.py
│       │   ├── test_graph_transactions.py
│       │   ├── test_json_source_execute_query.py
│       │   ├── test_metadata_enrichment.py
│       │   ├── test_nl_tools.py
│       │   ├── test_registry.py
│       │   ├── test_schema.py
│       │   ├── test_search_components.py
│       │   ├── test_semantic_types.py
│       │   ├── test_similarity_and_ranking.py
│       │   ├── test_sqlite_source.py
│       │   ├── test_stream_execute_query.py
│       │   ├── test_stream_source.py
│       │   ├── test_utils.py
│       │   ├── test_vector_execute_query.py
│       │   └── test_vector_source.py
│       ├── integration/                     # require external services (Redis, Postgres, MySQL, Neo4j)
│       │   ├── test_mysql_source.py
│       │   ├── test_neo4j_source.py
│       │   ├── test_neo4j_transactions.py
│       │   ├── test_postgres_source.py
│       │   ├── test_redis_registry.py
│       │   ├── test_redis_stream_source.py
│       │   ├── test_search_e2e.py
│       │   ├── test_search_scenarios.py
│       │   ├── test_sqlite_registry.py
│       │   └── test_sync_source_e2e.py
│       └── benchmarks/                      # LLM-backed NL2SQL, search, and enrichment benchmarks
│           ├── _discovery_runner.py         # shared runner for discovery benchmarks
│           ├── _set_retrieval_runner.py     # shared runner for set-retrieval benchmarks
│           ├── bird_converter.py            # converts BIRD benchmark format to blue-data queries
│           ├── bird_lake_benchmark.py       # BIRD data lake benchmark across multiple DBs
│           ├── bird_set_benchmark.py        # BIRD set-retrieval benchmark
│           ├── enrichment_benchmark.py
│           ├── finance_discovery_benchmark.py
│           ├── finance_set_benchmark.py     # finance set-retrieval benchmark
│           ├── nl2q_benchmark.py
│           ├── nl2q_enrichment_benchmark.py
│           ├── northwind_discovery_benchmark.py
│           ├── northwind_set_benchmark.py   # Northwind set-retrieval benchmark
│           └── search_benchmark.py
│
└── platform/                                # external interface services
    ├── api/                                 # REST API (blue-data-api PyPI package)
    │   ├── README.md                        # install, run, endpoint reference, configuration
    │   ├── pyproject.toml
    │   ├── src/registry_api/
    │   │   ├── main.py                      # FastAPI app; lifespan; uvicorn entry point (port 8000)
    │   │   ├── config.py                    # DataRegistry singleton from env vars
    │   │   ├── deps.py                      # FastAPI dependencies (registry injection)
    │   │   ├── models.py                    # Pydantic request/response models
    │   │   └── routers/
    │   │       ├── records.py               # /search, /records/* routes
    │   │       ├── sources.py               # /{source_name}/databases|collections|entities routes
    │   │       └── hierarchy.py             # hierarchy inspection routes
    │   └── tests/
    │       ├── conftest.py                  # mock DataRegistry fixture; TestClient
    │       ├── test_hierarchy.py
    │       ├── test_records.py
    │       └── test_sources.py
    ├── cli/                                 # CLI (blue-data-cli PyPI package)
    │   ├── README.md                        # install and command reference
    │   ├── pyproject.toml
    │   ├── src/registry_cli/
    │   │   ├── main.py                      # Click command groups: source, search
    │   │   └── config.py                    # DataRegistry singleton from env vars
    │   └── tests/
    │       ├── conftest.py
    │       └── test_cli.py
    ├── json-mcp/                            # MCP server for JSONSource operations
    │   ├── README.md                        # install, tool reference, Claude Desktop config
    │   ├── pyproject.toml
    │   ├── src/json_mcp/
    │   │   ├── server.py                    # fastmcp server; JSONSource tools
    │   │   └── config.py
    │   └── tests/
    │       └── test_tools.py
    └── registry-mcp/                        # MCP server for Registry/DataRegistry operations
        ├── README.md                        # install, tool reference, Claude Desktop config
        ├── pyproject.toml
        ├── src/registry_mcp/
        │   ├── server.py                    # fastmcp server; registry discovery tools
        │   └── config.py
        └── tests/
            └── test_tools.py
```

---

## Layout Rationale

### `lib/` — the Python library

All business logic lives under `lib/src/`. The `src/` layout prevents the package from being accidentally importable from the project root during development. `lib` is the only artifact published to PyPI as `blue-data`.

### Three independent hierarchies

The codebase implements three abstract hierarchies that never share base classes:

| Hierarchy | Base class | Purpose |
|-----------|-----------|---------|
| `source/source.py` | `DataSource` | External data: SQL, graph, stream, files, etc. |
| `source/json/json_source.py` | `JSONSource` | Registry persistence (get/set/delete a JSON tree) |
| `source/vector/vector_source.py` | `VectorSource` | Semantic search (create_index / upsert / knn) |

`DataRegistry` holds a `JSONSource` for record storage and a `VectorSource` for search — neither is a `DataSource` in the external-data sense, even though both inherit `DataSource` for the lifecycle/property protocol.

### Module-to-architecture mapping

| Module | Responsibility |
|--------|---------------|
| `source/source.py` | `DataSource` — lifecycle protocol; all `fetch_*`, `create_*`, `execute_query*`, `import_data`, `fetch_*_stats` |
| `core/schema.py` | `DataSchema` — in-memory entity/relation graph built during `fetch_database_collection_entities` |
| `source/json/json_source.py` | `JSONSource` — storage ABC for Registry; get/set/delete + execute_query dispatch |
| `source/vector/vector_source.py` | `VectorSource` — search index ABC; create_index/upsert/delete/knn + execute_query dispatch |
| `registry/registry.py` | `Registry` — generic key/value record store over any JSONSource |
| `registry/data_registry.py` | `DataRegistry` — Registry + typed source helpers + search engine wiring |
| `registry/enrichment/metadata.py` | `MetaData` — LLM + deterministic attribute/entity enrichment pipeline |
| `registry/enrichment/semantic_types.py` | `SemanticTypeInferencer` — deterministic column type inference |
| `registry/search/registry_search.py` | `RegistrySearch` — wires HybridSearch + RecordIndexer |
| `registry/search/hybrid_search.py` | `HybridSearch` — BM25 + vector score fusion |
| `utils/config/spec.py` | `ParamSpec`/`ConfigSpec` — a CLI's declared configuration parameters, their casts, and spec composition |
| `utils/config/profiles.py` | `ProfileStore` — read/write the `~/.<cli>/.profiles` INI file (mode `0600`) and the selected profile |
| `utils/config/resolve.py` | `ConfigResolver` — precedence (option > environment > profile > default), parameter inheritance, `$VAR` references, and `export()` into `os.environ` |
| `utils/config/secrets.py` | Encoding, decoding and masked display of secret values |

`utils/config/` deliberately imports no CLI framework, so it adds no dependencies: it decides *what to ask for* and *what a value resolves to*, while prompting and command wiring stay in each CLI. `blue-data-kb-source`'s `kb profile` group is the reference implementation.

### `platform/` — external interface services

Each service is an independent deployable unit with no business logic — all calls delegate to a `DataRegistry` singleton via the shared `config.py`.

| Service | Package | Port/Entry |
|---------|---------|-----------|
| `api/` | `blue-data-api` | Uvicorn, port 8000 |
| `cli/` | `blue-data-cli` | `blue-data` Click command |
| `registry-mcp/` | `blue-data-registry-mcp` | fastmcp stdio |
| `json-mcp/` | `blue-data-json-mcp` | fastmcp stdio |

### `tests/`

Library tests live under `lib/tests/`. The default `testpaths = ["tests/unit"]` means `pytest` with no flags runs only unit tests. Integration tests require the appropriate external services (Redis Stack, Postgres, MySQL, Neo4j) and must be run explicitly.
