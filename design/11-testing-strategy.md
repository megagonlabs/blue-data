# blue-data — Testing Strategy

## Overview

`blue-data` uses two test tiers for the core library and separate adapter tests for each platform service:

- **Unit tests** — run by default (`testpaths = ["tests/unit"]`); all external services mocked or replaced with in-memory implementations
- **Integration tests** — require live external services (Redis Stack, Postgres, MySQL, Neo4j); run explicitly
- **Benchmarks** — LLM-backed NL2SQL accuracy, search ranking, and enrichment quality; require API keys and external services

Platform adapter tests exercise the translation layer (HTTP routes, CLI commands, MCP tools) in isolation using mocked `DataRegistry`.

---

## 1. Tooling

| Tool | Package | Purpose |
|------|---------|---------|
| `pytest` | lib + all platforms | Test runner |
| `pytest-asyncio` | lib | `asyncio_mode = "auto"` for async test support |
| `pytest-cov` | lib | Coverage measurement |
| `httpx` | platform/api | FastAPI `TestClient` HTTP transport |

All tools are declared as `dev` dependencies in `lib/pyproject.toml` (lib) and `platform/api/pyproject.toml` (REST API).

---

## 2. Test Layout

```
lib/tests/
├── unit/                              # 28 test files; all I/O mocked or in-memory
│   ├── test_bayesian_network_source.py
│   ├── test_chromadb_vector_source.py
│   ├── test_data_registry_unit.py
│   ├── test_datasource_lifecycle.py
│   ├── test_execute_query_nl.py        # NL→native translation; mocked LLM
│   ├── test_export_data.py
│   ├── test_file_graph_source.py
│   ├── test_file_json_source.py
│   ├── test_file_source.py
│   ├── test_graph_execute_query.py
│   ├── test_graph_source.py
│   ├── test_graph_transactions.py
│   ├── test_json_source_execute_query.py
│   ├── test_metadata_enrichment.py     # MetadataEnricher; mocked LLM + sample data
│   ├── test_nl_tools.py               # execute_query_nl_tools; mocked Anthropic client
│   ├── test_registry.py
│   ├── test_schema.py                 # DataSchema add/get/to_str/from_json
│   ├── test_search_components.py      # BM25, HybridSearch, RecordIndexer
│   ├── test_semantic_types.py         # SemanticTypeInferencer; deterministic only
│   ├── test_similarity_and_ranking.py # cosine, score fusion
│   ├── test_sqlite_source.py          # SQLiteDBSource with a temp .db file
│   ├── test_stream_execute_query.py
│   ├── test_stream_source.py
│   ├── test_utils.py
│   ├── test_vector_execute_query.py   # VectorSource.execute_query op dispatch
│   └── test_vector_source.py          # MemoryVectorSource end-to-end
├── integration/                       # 10 test files; require external services
│   ├── test_mysql_source.py           # requires MySQL
│   ├── test_neo4j_source.py           # requires Neo4j
│   ├── test_neo4j_transactions.py     # requires Neo4j
│   ├── test_postgres_source.py        # requires Postgres
│   ├── test_redis_registry.py         # requires Redis Stack
│   ├── test_redis_stream_source.py    # requires Redis
│   ├── test_search_e2e.py             # requires Redis Stack (RedisVectorSource)
│   ├── test_search_scenarios.py       # requires Redis Stack
│   ├── test_sqlite_registry.py        # SQLite DataRegistry integration
│   └── test_sync_source_e2e.py        # full sync_source pipeline
└── benchmarks/                        # LLM + external services required
    ├── enrichment_benchmark.py        # enrichment quality on sample datasets
    ├── finance_discovery_benchmark.py # NL discovery on finance schema
    ├── nl2q_benchmark.py              # NL2SQL accuracy on curated query set
    ├── nl2q_enrichment_benchmark.py   # NL2SQL accuracy post-enrichment
    ├── northwind_discovery_benchmark.py
    └── search_benchmark.py            # hybrid search ranking quality

platform/api/tests/
├── conftest.py      # mock DataRegistry fixture; FastAPI TestClient
├── test_hierarchy.py
├── test_records.py
└── test_sources.py

platform/cli/tests/
├── conftest.py      # patched DataRegistry singleton
└── test_cli.py

platform/registry-mcp/tests/
└── test_tools.py

platform/json-mcp/tests/
└── test_tools.py
```

---

## 3. In-Process Test Doubles

### In-memory backends

Unit tests use in-process implementations instead of mocking at the call level:

| Real dependency | Test double | Why |
|----------------|-------------|-----|
| `RedisJSONSource` / `FileJSONSource` | `MemoryJSONSource` | No process required; dict-backed |
| `RedisVectorSource` / `ChromaDBVectorSource` | `MemoryVectorSource` | No process required; numpy-backed |
| SQLite files | `tempfile.NamedTemporaryFile` + `SQLiteDBSource` | Standard library; no server |

`MemoryJSONSource` and `MemoryVectorSource` run the same code paths as their production backends — they implement the same ABCs. This is the key invariant: the test double is not a mock of an interface, it is a real implementation of the same interface.

### Mocked LLM

Tests for `execute_query_nl`, `execute_query_nl_tools`, and `MetadataEnricher` mock the `anthropic.Anthropic` client via `unittest.mock.patch`. Tests assert on the prompt content sent to the client and on how the response is parsed into a native query or enrichment property, not on the LLM's answer quality.

```python
@patch("blue_data.source.source.anthropic.Anthropic")
def test_nl_tool_dispatches_execute_query(mock_client):
    mock_client.return_value.messages.create.return_value = _tool_response(
        "execute_query", {"query": "SELECT * FROM orders", "database": "main"}
    )
    source = SQLiteDBSource("mydb", properties={"dir": tmp_dir})
    result = source.execute_query_nl_tools("list all orders", llm_fn=mock_llm_fn)
    assert len(result) > 0
```

---

## 4. Unit Tests

Each unit test file covers one module. Tests assert on:

- Return value structure and field presence
- Correct dispatch of `execute_query` `op` values
- Error conditions: unsupported ops, missing required fields, type errors
- Registry path conventions: record keys, scope construction, `$` root sentinel
- `DataSchema` round-trip: `to_json()` / `from_json()` / `to_str()`
- Deterministic enrichment: `SemanticTypeInferencer` column type inference
- Search score fusion: BM25 and vector scores combined correctly by `HybridSearch`

**Example — VectorSource op dispatch:**

```python
def test_knn_with_embedding_alias(memory_vector_source):
    memory_vector_source.create_index("idx", "col", dim=4)
    memory_vector_source.upsert("col", "doc1", {"embedding": [1, 0, 0, 0], "text": "hello"})
    result = memory_vector_source.execute_query({
        "op": "VECTOR.KNN",
        "index": "idx",
        "embedding": [1, 0, 0, 0],  # 'embedding' key accepted as alias for 'vector'
        "k": 1,
    })
    assert result[0]["text"] == "hello"
```

**Example — Registry path convention:**

```python
def test_record_key_encodes_scope_and_type(registry):
    registry.register_record("northwind", "source", scope="/")
    record = registry.get_record("northwind", "source", scope="/")
    assert record["name"] == "northwind"
    assert record["type"] == "source"
    assert record["scope"] == "/"
```

---

## 5. Integration Tests

Integration tests exercise the full stack against real external services. They are excluded from the default `testpaths` and must be run with an explicit path.

### External service requirements

| Test file | Service required |
|-----------|----------------|
| `test_redis_registry.py`, `test_search_e2e.py`, `test_search_scenarios.py` | Redis Stack (port 6379) |
| `test_redis_stream_source.py` | Redis (port 6379) |
| `test_postgres_source.py` | PostgreSQL |
| `test_mysql_source.py` | MySQL |
| `test_neo4j_source.py`, `test_neo4j_transactions.py` | Neo4j (Bolt, port 7687) |
| `test_sqlite_registry.py`, `test_sync_source_e2e.py` | None (SQLite + MemoryVectorSource) |

Integration tests verify end-to-end correctness that cannot be checked with in-memory substitutes:

- `RedisJSONSource`: JSON.SET roundtrip, path scoping, namespace isolation
- `RedisVectorSource`: index creation, upsert, KNN accuracy
- `sync_source_e2e`: full DataRegistry.sync_source walk → register → search round-trip
- `search_e2e`: ingest records, run hybrid search, verify ranking

---

## 6. Benchmarks

Benchmarks measure accuracy (not speed) of LLM-backed features. They require `ANTHROPIC_API_KEY` and external databases.

| Benchmark | What it measures |
|-----------|----------------|
| `nl2q_benchmark.py` | NL2SQL accuracy: n questions against Northwind/Finance schemas; % correct |
| `nl2q_enrichment_benchmark.py` | NL2SQL accuracy after MetadataEnricher runs |
| `enrichment_benchmark.py` | Enrichment property correctness on known-answer column sets |
| `search_benchmark.py` | Hybrid search: P@k and MRR on curated relevance sets |
| `finance_discovery_benchmark.py` | End-to-end discovery flow on a finance schema |
| `northwind_discovery_benchmark.py` | End-to-end discovery flow on Northwind |

Results are recorded in `benchmarks/*.md` files committed to the repo.

---

## 7. Platform Adapter Tests

Each platform adapter is tested independently. The `DataRegistry` singleton is replaced with a `MagicMock` — adapter tests exercise the translation layer only.

### REST API (`platform/api/tests/`)

Uses FastAPI's `TestClient` (sync wrapper over ASGI). Tests assert on:
- HTTP status codes (200, 422, 404)
- Request body deserialization → `DataRegistry` method call arguments
- Response JSON structure

```python
def test_search_delegates_to_registry(client, mock_registry):
    mock_registry.search_records.return_value = [{"name": "orders", "type": "entity"}]
    resp = client.post("/search", json={"query": "customer orders", "k": 5})
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "orders"
    mock_registry.search_records.assert_called_once_with("customer orders", k=5)
```

### CLI (`platform/cli/tests/`)

Uses Click's `CliRunner`. The DataRegistry singleton is patched. Tests assert on:
- Exit codes
- Registry method call arguments
- Stdout format (plain text and `--json`)

---

## 8. Running Tests

```bash
# Unit tests (default — no external services)
pytest lib/tests/unit/ -v

# Integration tests (need Redis Stack, Postgres, MySQL, Neo4j)
pytest lib/tests/integration/ -v

# Search integration only (Redis Stack only)
pytest lib/tests/integration/test_search_e2e.py lib/tests/integration/test_search_scenarios.py -v

# SQLite integration (no external services)
pytest lib/tests/integration/test_sqlite_registry.py lib/tests/integration/test_sync_source_e2e.py -v

# REST API adapter tests
pytest platform/api/tests/ -v

# CLI adapter tests
pytest platform/cli/tests/ -v

# MCP adapter tests
pytest platform/registry-mcp/tests/ platform/json-mcp/tests/ -v

# Coverage report (unit tests)
pytest lib/tests/unit/ --cov=blue_data --cov-report=term-missing
```
