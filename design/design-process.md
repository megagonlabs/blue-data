# Design Process

## Document organization

The `design/` directory contains 13 numbered documents that capture the full design of blue-data in a fixed, reviewable sequence:

| File | Topic |
|---|---|
| `01-overview.md` | Problem statement, objectives, what blue-data does |
| `02-scenarios.md` | Concrete motivating scenarios that drive design decisions |
| `03-high-level-architecture.md` | Component map and data flow overview |
| `04-detailed-architecture.md` | Per-component design: DataSource, Registry, DataRegistry, search, enrichment |
| `05-software-stack.md` | Language, frameworks, and runtime dependencies |
| `06-library.md` | Library package structure and import conventions |
| `07-repo-organization.md` | Directory layout, naming, and module boundaries |
| `08-coding-style.md` | Linting, typing, naming, and testing conventions |
| `09-api-interface-spec.md` | REST API contract and OpenAPI alignment |
| `10-data-model.md` | Registry record schema and JSONSource path conventions |
| `11-testing-strategy.md` | Unit vs integration tests, fixture policy, coverage targets |
| `12-deployment-ops.md` | Container, Redis Stack, and secrets configuration |
| `13-decision-log.md` | Architectural Decision Records (ADRs) for significant decisions |

## When to update these documents

- **Add a new ADR** to `13-decision-log.md` any time a significant design decision is made — a new abstraction, a change to path conventions, a backend choice, or a deliberate deviation from a prior decision. ADRs record what was decided, why, and what consequences follow.
- **Update the relevant numbered document** when the implementation diverges from the written design. The documents should reflect the current state of the code, not the original intent.
- **Do not add a new numbered file** — the 13-file sequence is complete. Append to `13-decision-log.md` for new decisions.

## Design principles

These principles inform decisions across the codebase:

1. **Three distinct hierarchies** — `DataSource` (external data), `JSONSource` (registry state), and `VectorSource` (search index) are independent and must not be conflated.
2. **Synchronous library** — the core library has no `async`/`await`. Platform layers (FastAPI, MCP) are async; they call synchronous library methods directly.
3. **Registry path convention** — records are keyed by `/{scope}/{type}/{name}`. See [ADR-001 in 13-decision-log.md](13-decision-log.md#adr-001--registry-path-convention-scopetypename).
4. **Stats before enrichment** — enrichment reads sample values from stats; calling it without stats first produces empty results. The pipeline order (sync → stats → enrich) is enforced by design.
5. **`rebuild` three-state flag** — `True` = force index, `False` = suppress, `None` = defer to instance default. This lets callers opt out of indexing for bulk operations.
