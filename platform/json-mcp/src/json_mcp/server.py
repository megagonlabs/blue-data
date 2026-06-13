"""blue-data JSON MCP server.

Exposes raw JSONSource operations (get/set/delete/list_keys) as MCP tools.
Useful for direct key-value inspection and manipulation of the backing store
without going through the DataRegistry abstraction.

Tools:
    json_get        — read a value at a path
    json_set        — write a value at a path
    json_delete     — delete a value at a path
    json_list_keys  — list all known keys (memory store only)
    json_get_all    — dump the entire store
"""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from json_mcp.config import get_store

mcp = FastMCP(
    "blue-data-json",
    instructions=(
        "Provides direct read/write access to the blue-data JSONSource backing store. "
        "Use json_get / json_set / json_delete for targeted operations, "
        "json_list_keys to enumerate keys, and json_get_all to dump the full store."
    ),
)


@mcp.tool()
def json_get(path: str) -> dict:
    """Read the value stored at *path* in the JSONSource.

    Use '$' or an empty string to read the entire root document.
    """
    store = get_store()
    value = store.get(path)
    return {"path": path, "value": value}


@mcp.tool()
def json_set(path: str, value: Any) -> dict:
    """Write *value* at *path* in the JSONSource.

    Use '$' or an empty string to overwrite the root document.
    """
    store = get_store()
    store.set(path, value)
    return {"status": "ok", "path": path}


@mcp.tool()
def json_delete(path: str) -> dict:
    """Delete the value at *path* from the JSONSource.

    Use '$' or an empty string to clear the entire store.
    """
    store = get_store()
    store.delete(path)
    return {"status": "ok", "path": path}


@mcp.tool()
def json_list_keys(prefix: Optional[str] = None) -> dict:
    """List all keys in the JSONSource.

    Optionally filter to keys that start with *prefix*.
    Works with both MemoryJSONSource and FileJSONSource.
    """
    store = get_store()
    root = store.get(None)
    if not isinstance(root, dict):
        return {"keys": []}
    keys = list(root.keys())
    if prefix:
        keys = [k for k in keys if k.startswith(prefix)]
    return {"keys": sorted(keys)}


@mcp.tool()
def json_get_all() -> dict:
    """Return the entire contents of the JSONSource.

    For large stores this can be verbose — prefer json_get with a specific path
    when you know what you're looking for.
    """
    store = get_store()
    return {"value": store.get(None)}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
