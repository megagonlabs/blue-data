# Configuration

All platform components (API, CLI, MCP servers) are configured via environment variables. Copy `example.envrc` to `.envrc` and fill in your values — `.envrc` is gitignored and never committed.

```bash
cp example.envrc .envrc
source .envrc
```

Variables can also be set inline or exported in your shell. The sections below document every supported variable, its default, and when it is required.

## Profiles (`blue_data.utils.config`)

A CLI in this family does not have to make users export anything. `blue_data.utils.config` gives it named **profiles** — sets of these same variables, stored per CLI in `~/.<cli>/.profiles` — so switching environments is one command instead of a shell full of exports.

```python
from blue_data.utils.config import base_spec, build_resolver, load_spec

spec = base_spec().merged_with(load_spec("my_cli/profile_spec.json"))
resolver = build_resolver(spec, home="~/.mycli")
resolver.export()          # resolved values -> os.environ, for everything that reads them
```

`ProfileStore.initialize()` creates the `default` profile on first run, so a CLI needs no setup step before it works. A CLI declares its own parameters in a JSON spec and merges them with `base_spec()`, which holds the family-wide ones (`OPENAI_API_KEY`, `BLUE_DATA_LLM_MODEL`, `BLUE_DATA_CLI_FORMAT`, …). Each entry declares a `default`, a `prompt` shown during interactive configuration, whether it is `required` (which selects what a walkthrough asks about), and a `cast` — `directory`, `file`, `str`, `int`, `float`, `bool` or `secret`.

Resolution order is **command option > environment variable > profile > spec default**, and a parameter may `inherit` from others, so `MYCLI_EXTRACTION_LLM_MODEL` can fall back to `MYCLI_LLM_MODEL` and then to `BLUE_DATA_LLM_MODEL`.

Secret parameters are stored either encoded, or as a `$VAR` reference resolved from the environment at use. The profiles file is written `0600`, and nothing decodes a secret for display. The encoding is obfuscation rather than encryption — the file mode is the real protection, and the reference form is what keeps a secret off disk entirely.

This package is deliberately free of any CLI framework, so it adds no dependencies: it decides *what to ask for* and *what a value resolves to*, while prompting and command wiring stay in each CLI. `blue-data-kb-source`'s `kb profile` group is the reference implementation.

---

## Store

Controls where the registry state is persisted.

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_STORE` | `memory` | Persistence backend: `memory`, `redis`, or `file` (json-mcp only) |
| `BLUE_DATA_REGISTRY_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Required when `BLUE_DATA_REGISTRY_STORE=redis` |
| `BLUE_DATA_REGISTRY_REDIS_NAMESPACE` | `blue_data` | Key namespace prefix in Redis. Isolates multiple registry instances on the same server |
| `BLUE_DATA_REGISTRY_FILE` | `blue_data_store.json` | Path to JSON file. Required when `BLUE_DATA_REGISTRY_STORE=file` (json-mcp only) |

> **Redis Stack required**: `BLUE_DATA_REGISTRY_STORE=redis` uses `JSON.SET` and `FT.CREATE` commands only available in Redis Stack (`redis-stack-server`), not plain Redis.

---

## LLM

Enables AI-augmented metadata enrichment. Leave `BLUE_DATA_LLM_PROVIDER` blank to run in deterministic-only mode (no API key needed).

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_LLM_PROVIDER` | _(empty)_ | LLM provider: `anthropic` or `openai`. Leave blank to disable LLM enrichment |
| `BLUE_DATA_LLM_MODEL` | `claude-opus-4-8` (anthropic) / `gpt-4o` (openai) | Model name passed to the provider API |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required when `BLUE_DATA_LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | _(empty)_ | Required when `BLUE_DATA_LLM_PROVIDER=openai` |

---

## Search tuning

Controls the hybrid search engine inside `DataRegistry`. Defaults are tuned for general use — adjust if your registry has specific recall/precision requirements.

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_REGISTRY_VECTOR_DIM` | `1536` | Embedding vector dimension. Must match your embedding model's output size |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT` | `0.3` | Weight of BM25 keyword score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT` | `0.7` | Weight of vector similarity score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT` | `0.15` | Weight of value-relevance score in the combined ranking |
| `BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD` | `0.0` | Minimum BM25 score for a record to be considered |
| `BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD` | `0.5` | Minimum vector similarity score for a record to be considered |
| `BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD` | `0.36` | Minimum combined score for a record to appear in results |
| `BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL` | `true` | Enable hierarchical search — propagates child scores to parent records when searching by `database` or `collection` type |

Search weights do not need to sum to 1 — they are normalized automatically.

---

## Sources

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_SOURCES_CONFIG` | _(empty)_ | Path to a JSON file that pre-loads data sources into the registry at startup |

Source config file format:

```json
{
  "sources": [
    {
      "type": "sqlite",
      "name": "mydb",
      "properties": { "connection": { "database_directory": "/data/dbs" } }
    },
    {
      "type": "postgres",
      "name": "prod",
      "properties": { "connection": { "host": "localhost", "port": 5432, "database": "myapp", "user": "postgres", "password": "" } }
    }
  ]
}
```

Supported source types: `sqlite`, `postgres`, `mysql`, `mongodb`. (`neo4j` and `file` sources exist as DataSource classes but are not yet wired into the config loader.)

---

## REST API (`blue-data-api`)

Controls the REST API's network exposure, authentication, and write access.

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_API_HOST` | `127.0.0.1` | Bind address. Defaults to loopback; set `0.0.0.0` to expose on all interfaces (e.g. in a container) |
| `BLUE_DATA_API_PORT` | `8000` | Port to bind |
| `BLUE_DATA_API_KEY` | _(empty)_ | Auth is **mandatory by default**. Clients send this key via `X-API-Key: <key>` or `Authorization: Bearer <key>`. If unset, every data endpoint returns `401` unless `BLUE_DATA_API_AUTH_DISABLED` is set. `/health` and the docs routes are always open |
| `BLUE_DATA_API_AUTH_DISABLED` | `false` | Explicit opt-out to run **without** auth (dev only). Ignored when `BLUE_DATA_API_KEY` is set |
| `BLUE_DATA_API_ALLOW_WRITES` | `false` | When `true`, `POST /{source}/query` honors `commit=true` to execute writes. Otherwise the endpoint is read-only and a `commit=true` request returns `403` |

State-changing routes (`POST`/`PUT`/`PATCH`/`DELETE`) reject browser-simple content types (`application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`) with `415` as CSRF protection — use `application/json`.

> **Secure defaults:** the API binds loopback and requires auth out of the box. For a deployment reachable by other hosts, set `BLUE_DATA_API_HOST`, set `BLUE_DATA_API_KEY` (don't use `BLUE_DATA_API_AUTH_DISABLED`), and enable `BLUE_DATA_API_ALLOW_WRITES` only if clients legitimately need to write.
