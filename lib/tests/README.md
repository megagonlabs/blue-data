# Tests

## Structure

```
lib/tests/
├── unit/          — fast, no external dependencies (SQLite + in-memory backends only)
├── integration/   — require external servers (Postgres, MySQL, Neo4j, Redis)
└── benchmarks/    — NL2SQL quality benchmark (requires Anthropic API key)
```

## Running tests

### Unit tests (default)

No external servers needed. This is what runs by default via `pytest`.

```bash
pip install -e lib/[dev]
python3 -m pytest lib/tests/unit/ -v
```

### Integration tests

Each integration test file auto-skips if the required server is not reachable — they will not fail, just show `s` in the output.

| File | Requires | Default connection |
|---|---|---|
| `test_postgres_source.py` | PostgreSQL | `localhost:5432`, user=`postgres`, no password |
| `test_mysql_source.py` | MySQL | `localhost:3306`, user=`root`, no password |
| `test_neo4j_source.py` | Neo4j | `bolt://localhost:7687`, no auth |
| `test_neo4j_transactions.py` | Neo4j | `bolt://localhost:7687`, no auth |
| `test_redis_registry.py` | Redis Stack | `localhost:6379` |
| `test_redis_stream_source.py` | Redis Stream | `localhost:6379` |
| `test_sqlite_registry.py` | — | SQLite only, always runs |
| `test_search_e2e.py` | — | SQLite only, always runs |
| `test_sync_source_e2e.py` | — | SQLite only, always runs |

Override connection details via environment variables:

```bash
# PostgreSQL
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=

# MySQL
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=

# Neo4j
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=
```

Run a specific integration file once the server is up:

```bash
# start Postgres (example with Docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD="" -e POSTGRES_HOST_AUTH_METHOD=trust postgres

python3 -m pytest lib/tests/integration/test_postgres_source.py -v
```

Run the full suite (unit + integration, skipping unavailable servers):

```bash
python3 -m pytest lib/tests/ -v
```

## Benchmarks

See [benchmarks/README.md](benchmarks/README.md) for the NL2SQL enrichment benchmark. It requires an OpenAI or Anthropic API key and is not part of the normal test run.
