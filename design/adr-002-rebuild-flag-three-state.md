# ADR-002: The `rebuild` Flag Is Three-State (`True` / `False` / `None`)

**Status:** Accepted

## Context

Every registry write method (`register_record`, `update_record`, `delete_record`) can trigger a re-index of the record into the vector search index. We need callers to control when re-indexing happens, because:

- Re-indexing on every write during a bulk sync is expensive (one embedding call per record).
- Suppressing re-indexing entirely loses the benefit of keeping search current.
- Different callers have different needs: a one-off write should index immediately; a bulk import should defer and index once at the end.

A simple boolean `rebuild=True/False` was considered but rejected.

## Decision

`rebuild` is a three-state flag on all registry write methods:

| Value | Meaning |
|---|---|
| `True` | Force re-index this record immediately, regardless of instance default. |
| `False` | Suppress re-indexing for this write. |
| `None` (default) | Defer to `DataRegistry._rebuild` instance-level default. |

`DataRegistry._rebuild` is set at construction time and applies to all writes that pass `rebuild=None`. This lets callers opt in or out per-call without changing the instance default.

## Consequences

**Good:**
- Bulk operations (sync, stats collection, enrichment) pass `rebuild=False` to suppress per-record indexing, then call a single bulk re-index at the end — O(n) instead of O(n²).
- One-off writes (single `update_record` call) default to `None`, which picks up the instance policy without requiring the caller to know about it.
- Tests can set `DataRegistry(_rebuild=False)` globally and never pay embedding costs.

**Trade-off:**
- Three states are less obvious than a boolean. Callers must understand that `None` is not the same as `False`.
- The instance-level default adds implicit state that can surprise callers who don't know what `_rebuild` is set to.
