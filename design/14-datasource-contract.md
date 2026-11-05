# 14 — The DataSource contract

`DataSource` (`blue_data/source/source.py`) is the boundary every source — built-in
and sibling (doc, kb, llm, user, web) — implements so that `DataRegistry` and the
platform surfaces (MCP / REST / CLI) can drive them uniformly. The base class ships
no-op defaults; this document is the **normative contract** those defaults stand in
for, and it is enforced by the conformance kit in §7.

This contract is cross-repo (finding XR-02 / issue #110): each source repo is expected
to satisfy it and to run the conformance kit (§7) in CI.

## 1. Query results are `list[dict]`

`execute_query(query, database=None, collection=None, optional_properties=None)` and
`execute_query_nl(query, database=None, collection=None, schema=None, llm_fn=None,
optional_properties=None)` MUST return a **`list` of `dict`** rows (possibly empty).

- No tuples, scalars, or bare generators. A caller (e.g. the planner's `_as_table`)
  must be able to treat the result as a list of row objects without special-casing
  per source.
- **Side data** (a session id, a cursor, provenance) does NOT ride along as a second
  tuple element. It travels through a documented out-channel — a key on the rows, a
  property written back to the registry record, or an explicit accessor — never by
  changing the return *shape*.

## 2. The NL-query signature is fixed

`execute_query_nl` MUST accept exactly the keyword arguments the registry passes:
`query`, `database`, `collection`, `schema`, `llm_fn`, `optional_properties`
(a source may ignore any it does not use, or accept `**kwargs`). Renaming `query`
to `text`, or dropping `schema`/`llm_fn`, breaks `DataRegistry.execute_query_nl`.

## 3. Properties: reserved and shared-optional

A source's `properties` dict is the **only** state used to rebuild it (§4). Two groups
of keys are reserved by the framework and MUST be tolerated (accepted, not required,
and may be ignored) by every source:

- **Reserved** — written/read by the registry:
  - `_class` — fully-qualified class path, injected by `register_source`; used by
    `connect_source` to rebuild.
  - `metadata` — source/entity metadata the registry attaches after `sync_source`.
- **Shared optional** — passed in `optional_properties` on a query:
  - `commit` — `False`/absent means read-only; a source that cannot write MUST ignore
    it on a read rather than reject the call.

A source MUST NOT raise merely because it received a reserved or shared-optional key
it does not use.

### Declaring read and write ops (read-only is deny-by-default)

A source whose `execute_query` takes dict ops (`{"op": "...", ...}`, or the same object
as a JSON string) MUST declare every op it serves in exactly one of two class attributes:

- `_READ_OPS: frozenset` — ops that do not change data;
- `_WRITE_OPS: frozenset` — ops that do.

`DataRegistry.execute_query` — and so the CLI's `source query`, the REST
`POST /{source}/query` and the MCP `execute_query` tool — runs a dict or JSON op
without `optional_properties["commit"]` **only when the op is in `_READ_OPS`**. An op in
`_WRITE_OPS`, or one the source does not declare at all, needs `commit` and is refused
on every read-only path. A source that forgets an op therefore loses read-only access to
it rather than gaining unguarded writes (#237). Op names are matched upper-cased, so
declare them upper-case. A dict without an `"op"` key counts as the op `None`; a source
whose op-less dicts are reads (e.g. `FileSource`'s legacy filter) lists `None` in
`_READ_OPS`. Plain query strings (SQL, Cypher) are not classified here: the source
guards them itself, as `SQLSource.execute_query` does with a read-only connection.
An op whose effect depends on its arguments is classified on its arguments: the source
overrides `_query_requires_commit` and guards the op in `execute_query` as well, as
`MongoDBSource` does for an `AGGREGATE` whose pipeline holds a `$out` or `$merge`
stage (#248).

```python
class MySource(DataSource):
    _READ_OPS = frozenset({"MY.SEARCH", "MY.GET"})
    _WRITE_OPS = frozenset({"MY.INGEST", "MY.DELETE"})
```

The default `_is_write_native_query` used by `execute_query_nl` applies the same rule to
NL-generated dict ops. Each source SHOULD have a unit test asserting that every op it
serves is in exactly one of the two sets (see `lib/tests/unit/test_write_guard_all_sources.py`).

### Declaring per-process (transient) properties

Some properties describe only the process that registered the source, not its
reconstructible configuration. A source lists these in a class attribute:

- `_transient_properties: frozenset` — top-level property keys that are **not** persisted.

`DataRegistry.register_source` drops these keys (after credential sanitising) before
storing the record, so a source the registry rebuilds in another process gets the class
default rather than the registering process's value. For example, a `UserSource` declares
`_transient_properties = frozenset({"console"})`: a source registered with `console=True`
from an interactive script must not be rebuilt with `console=True` inside a stdio MCP
server or an API process, where a clarification prompt would corrupt the protocol stream
or block an HTTP request on the server's own stdin (#250). This is distinct from
credential stripping (§4): a transient property is dropped because it is process-scoped,
not because it is a secret.

```python
class UserSource(DataSource):
    _transient_properties = frozenset({"console"})
```

## 4. Reconstructible from properties alone

A source MUST be fully reconstructible from `(name, properties)`:

```python
rebuilt = DataSource.instantiate(properties["_class"], name, properties=properties)
```

`rebuilt` must answer the same queries as the original. This is kb's pattern. It means
**no required constructor argument may live outside `properties`** — an embedding model,
vector store, classifier or record store passed as a positional constructor object makes
the rebuilt object inert and violates the contract. Such collaborators must be derived
from `properties` (e.g. a model name + factory) so a registry that only has the stored
record can bring the source back to life.

### Credentials: `<key>_env` references

Because `properties` is the only rebuild state **and** the registry strips literal
credentials before persisting a record (§3), a secret cannot be stored directly. Store a
**reference** instead: for any connection key `<key>`, a sibling `<key>_env` whose value
is the *name of an environment variable* holding the secret. The reference is persisted
and survives a rebuild; the secret is read from the environment at connect time and never
written to the store. This is not source-specific — `DataSource._start_connection`
resolves and strips every `<key>_env` before calling `_connect`, so it applies to every
source and every key (`password_env`, `token_env`, `api_key_env`, …). An explicit
non-empty literal wins over the reference; an empty/default value does not mask it; the
reference is always dropped before reaching a driver. A source MUST read its credentials
from the connection mapping `_connect` receives (not re-read `self.properties`) so this
resolution is honoured; the base provides it so no source reimplements it.

## 5. NL tool signatures

`get_nl_tools()` returns the tool list; `execute_nl_tool(name, tool_input, database=None,
collection=None, optional_properties=None, read_only=True)` dispatches one call. The base
tools and the stats methods they call are part of the contract, including
`fetch_entity_stats(..., row_sample_size=...)` — the `get_sample` tool passes
`row_sample_size`, so an override either accepts it or accepts `**kwargs`. (The base
dispatch only forwards `row_sample_size` to implementations that declare it.)

## 6. No async overrides of sync methods

The base `DataSource` methods are synchronous. A subclass MUST NOT override a sync base
method with an `async def` (e.g. `async def fetch_database_schema`): the registry calls
them synchronously and an awaitable return breaks every caller. A source that needs async
IO runs it internally (e.g. via a thread / its own loop) and returns a concrete value.

## 7. Enforcement — the conformance kit

`blue_data.testing.conformance.DataSourceConformance` is a pytest-importable mixin that
asserts §1–§6. Each source repo subclasses it and provides a `data_source` fixture (and,
to enable the behavioural checks, a `sample_query`):

```python
from blue_data.testing.conformance import DataSourceConformance

class TestMySourceConformance(DataSourceConformance):
    @pytest.fixture
    def data_source(self):
        return MySource("t", properties={"connection": {...}})

    @pytest.fixture
    def sample_query(self):
        return ("SELECT 1 AS n", {"database": "t"})   # (query, kwargs); omit to skip behavioural checks
```

Structural checks (signature, async-override, reconstructible, reserved/shared
properties, disjoint `_READ_OPS`/`_WRITE_OPS`) always run; behavioural checks
(`list[dict]`, `commit` accepted, the sample read allowed without `commit`) run when a
`sample_query` is supplied. Every source repo SHOULD run this in CI (finding XR-02).
