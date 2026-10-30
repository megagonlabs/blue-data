# Extending blue-data

## Implementing a new DataSource

Subclass `DataSource` and override the methods your backend supports:

```python
from blue_data.source.source import DataSource

class MySource(DataSource):
    def fetch_databases(self) -> list[str]: ...
    def fetch_database_collections(self, database: str) -> list[str]: ...
    def fetch_database_collection_entities(self, database: str, collection: str) -> dict: ...
    def execute_query(self, query, database=None, collection=None, optional_properties=None): ...
```

`fetch_database_collection_entities` should return a dict keyed by entity name. Each value follows the `DataSchema` entity format:

```python
{
  "users": {
    "name": "users",
    "properties": {},
    "contents": {
      "attributes": {
        "id":   {"name": "id",   "info": {"type": "INTEGER"}, "description": None},
        "name": {"name": "name", "info": {"type": "TEXT"},    "description": None},
      }
    }
  }
}
```

All methods have no-op defaults in the base class — override only what your backend supports.

### Declare read and write ops

If `execute_query` takes dict ops (`{"op": "MY.SEARCH", ...}`), declare every op in exactly one of `_READ_OPS` or `_WRITE_OPS`:

```python
class MySource(DataSource):
    _READ_OPS = frozenset({"MY.SEARCH", "MY.GET"})
    _WRITE_OPS = frozenset({"MY.INGEST", "MY.DELETE"})
```

Read-only is deny-by-default: `DataRegistry.execute_query` (and the CLI, REST and MCP surfaces built on it) runs an op without `optional_properties={"commit": True}` only when it is in `_READ_OPS`. A write op, or an op you did not declare, is refused with `ValueError` unless `commit` is set. Plain query strings are not classified; guard them in your own `execute_query` (as `SQLSource` does). See [design/14 §3](../design/14-datasource-contract.md#3-properties-reserved-and-shared-optional).

---

## Extending NL translation

The default NL-to-query pipeline uses an LLM. To plug in rule-based or DSL translation for a new source, override `translate_nl_to_native_query` — the single hook point for translation strategy:

```python
class MySource(DataSource):
    def translate_nl_to_native_query(self, query, schema, llm_fn):
        # llm_fn is available but can be ignored for rule-based translation
        return my_dsl_parser(query)
```

Override `execute_query_nl` instead only when the *execution shape* differs from a plain `execute_query` call — for example, MongoDB wraps the filter in a `FIND` op dict. Sources that only need a different *translation* strategy should override `translate_nl_to_native_query` instead.
