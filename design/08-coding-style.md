# blue-data — Coding Style

## Tools

| Tool | Role |
|------|------|
| `ruff` | Linter + formatter (replaces Black, isort, flake8) |
| `pyright` (strict) | Static type checker |
| `pytest` | Test runner |

All three are declared as `dev` dependencies. CI fails on any lint, type, or test failure.

---

## Python Version and Annotations

- Minimum Python: **3.10**
- All files begin with `from __future__ import annotations` to enable PEP 604 union syntax (`X | Y`) and postponed annotation evaluation in ABCs.

---

## Linting and Formatting

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

- `ruff format` is the formatter (Black-compatible, 100-character lines).
- `ruff check --fix` auto-corrects safe lint violations.
- Imports are sorted with `I` rules: stdlib → third-party → local, alphabetical within each group.

---

## Type Annotations

- **All** public functions and methods carry full type annotations (parameters + return type).
- `pyright --strict` must pass with zero errors.
- Use `X | None` (not `Optional[X]`) with `from __future__ import annotations`.
- Use `list[X]` / `dict[K, V]` / `tuple[X, ...]` (not `List`, `Dict`, `Tuple`).
- `Any` is allowed only where the concrete type is genuinely unknown (e.g., JSONSource values, query result rows, DataSource property dicts).

---

## Synchronous Library

The core library (`lib/`) is **synchronous**. There is no `async`/`await` in `DataSource`, `JSONSource`, `VectorSource`, `Registry`, or `DataRegistry`. The REST API uses FastAPI async route handlers, but handlers call synchronous library methods directly.

---

## Naming

| Kind | Convention | Example |
|------|-----------|---------|
| Modules | `snake_case` | `data_registry.py`, `registry_search.py` |
| Classes | `PascalCase` | `DataRegistry`, `Registry`, `MemoryJSONSource` |
| Functions / methods | `snake_case` | `sync_source`, `fetch_databases`, `search_records` |
| Constants | `UPPER_SNAKE_CASE` | `BLUE_DATA_REGISTRY_STORE`, `_PATH_SEP` |
| Private helpers | `_leading_underscore` | `_require_source`, `_on_record_changed` |
| Type aliases | `PascalCase` | `RecordDict = dict[str, Any]` |

Op code strings on `VectorSource` follow a `NAMESPACE.VERB` pattern: `VECTOR.CREATE_INDEX`, `VECTOR.UPSERT`, `VECTOR.DELETE`, `VECTOR.KNN`.

Registry path keys follow `{scope}/{type}/{name}` — see [adr-001-registry-path-convention.md](adr-001-registry-path-convention.md).

---

## Abstract Base Classes

- Every hierarchy (`DataSource`, `JSONSource`, `VectorSource`) exposes an ABC.
- ABCs use `abc.ABC` + `@abstractmethod`. No shared initialization in ABCs unless required by the protocol.
- Concrete backends live in named subdirectories: `source/sql/sqlite/`, `source/json/redis/`, `source/vector/redis/`.
- ABCs and their concrete implementations are exported from the package `__init__.py`.

---

## `fetch_*` vs `create_*` naming

`DataSource` methods follow a consistent verb pattern:

| Verb | Meaning |
|------|---------|
| `fetch_*` | Read from a live source; may make a database call |
| `create_*` | Write to a live source (create a database, table, etc.) |
| `execute_query` | Ad-hoc query; returns rows |
| `fetch_*_stats` | Collect statistics; may make aggregate queries |

Subclasses override only the methods they support — no-op default implementations are provided in the base class.

---

## Docstrings

- Single-line docstring for any public method whose name does not make its contract obvious.
- No multi-line docstrings unless a subtlety is non-obvious from the signature (hidden constraint, invariant, side-effect).
- Do **not** document what the code does — document **why** or **when** if surprising.

---

## Error Handling

- Domain errors are plain `Exception` subclasses with descriptive messages — there is no `RegistryError` base yet.
- Only catch at system boundaries (route handlers, CLI command functions, MCP tool handlers) and convert to HTTP status codes, CLI exit codes, or JSON error objects.
- `_wrap()` in `hierarchy.py` catches `Exception` and re-raises as `HTTPException(500)` — this is the only broad catch in the codebase and is intentional for the REST API layer.
- `_require_source()` raises `HTTPException(404)` immediately when a source is not found — never returns `None` to a route handler.

---

## Deferred Imports for Optional Backends

Optional backends are deferred-imported at construction time in `config.py`:

| Package | Deferred in | When used |
|---------|------------|-----------|
| `redis` | `build_store()` | `BLUE_DATA_REGISTRY_STORE=redis` |
| `anthropic` | `build_enricher()` | `BLUE_DATA_LLM_PROVIDER=anthropic` |
| `openai` | `build_enricher()` | `BLUE_DATA_LLM_PROVIDER=openai` |

`pandas` and `numpy` are hard dependencies — imported at module top-level.

---

## File Layout

Each module follows this order:

1. `from __future__ import annotations`
2. stdlib imports
3. third-party imports
4. local imports
5. module-level constants / type aliases
6. class or function definitions

---

## Testing Style

- Test file names: `test_{module_name}.py`.
- Test function names: `test_{what}_{condition}`.
- Use real in-process doubles (`MemoryJSONSource`, `MemoryVectorSource`) — never mock internal collaborators.
- Mock only external APIs (`anthropic.Anthropic`, `openai.OpenAI`) via `unittest.mock.patch`.
- `DataRegistry(_rebuild=False)` is the standard test construction — suppresses embedding calls in all registry writes.
- Unit tests run with `testpaths = ["tests/unit"]` (default). Integration tests require Redis Stack.
