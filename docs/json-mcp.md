# json-mcp

MCP server that exposes raw `JSONSource` operations as tools for LLM clients
(Claude Desktop, Claude Code, and any MCP-compatible host).

Unlike `registry-mcp`, this server operates directly on the key/value store —
no `DataRegistry`, no source adapters, no enrichment. It is useful for
inspecting or editing registry state at the raw storage level, or for using the
JSONSource as a general-purpose persistent key/value store from an LLM session.

Supports **memory** and **file** backends only. Redis is intentionally excluded
— use `registry-mcp` if you need a shared, persistent registry.

---

## Installation

```bash
cd platform/json-mcp

# Install the core library first
pip install -e ../../lib

# Install the MCP server
pip install -e .
```

---

## Running

```bash
# Default: ephemeral in-memory store
blue-data-json-mcp

# Persistent file-backed store
BLUE_DATA_STORE=file \
BLUE_DATA_FILE=/path/to/store.json \
    blue-data-json-mcp
```

---

## Claude Desktop integration

Add to `~/.config/claude-desktop/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blue-data-json": {
      "command": "blue-data-json-mcp"
    }
  }
}
```

With a persistent file store:

```json
{
  "mcpServers": {
    "blue-data-json": {
      "command": "blue-data-json-mcp",
      "env": {
        "BLUE_DATA_STORE": "file",
        "BLUE_DATA_FILE": "/path/to/store.json"
      }
    }
  }
}
```

If `blue-data-json-mcp` is not on the system PATH, use the full path:

```json
{
  "mcpServers": {
    "blue-data-json": {
      "command": "/path/to/venv/bin/blue-data-json-mcp"
    }
  }
}
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `BLUE_DATA_STORE` | `memory` | `memory` — ephemeral in-process dict. `file` — persists to a JSON file on disk. |
| `BLUE_DATA_FILE` | `blue_data_store.json` | Path to the JSON file. Used only when `BLUE_DATA_STORE=file`. |

---

## Tool reference

### `json_get`

Read the value stored at a path.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` | Key path to read. Use `$` or empty string to read the entire root document. |

Returns `{"path": "<path>", "value": <stored value or null>}`.

---

### `json_set`

Write a value at a path.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` | Key path to write. Use `$` or empty string to overwrite the root document. |
| `value` | `any` | Value to store. Can be any JSON-serializable type. |

Returns `{"status": "ok", "path": "<path>"}`.

---

### `json_delete`

Delete the value at a path.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` | Key path to delete. Use `$` or empty string to clear the entire store. |

Returns `{"status": "ok", "path": "<path>"}`. Deleting a missing key does not raise an error.

---

### `json_list_keys`

List all top-level keys in the store.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prefix` | `str \| None` | `None` | If provided, return only keys starting with this prefix. |

Returns `{"keys": ["key1", "key2", ...]}` (sorted alphabetically).

---

### `json_get_all`

Dump the entire contents of the store.

Returns `{"value": { <all keys and values> }}`.

For large stores this can be verbose — prefer `json_get` with a specific path when you know what you're looking for.

---

## Typical session

```
# Inspect the current state of the store
json_get_all()

# Read a specific registry record written by DataRegistry
json_get("/source/sqlite/database/mydb/collection/public/entity/orders")

# Patch a description directly (bypasses DataRegistry validation)
json_set(
    "/source/sqlite/database/mydb/collection/public/entity/orders",
    {"name": "orders", "type": "entity", "description": "Customer orders table"}
)

# Find all keys under a source
json_list_keys("/source/sqlite")

# Remove a stale key
json_delete("/source/sqlite/database/old_db")

# Clear the entire store
json_delete("$")
```

---

## Path conventions

The JSONSource uses the same path format that `DataRegistry` writes:

```
/source/{source_name}
/source/{source_name}/database/{db}
/source/{source_name}/database/{db}/collection/{col}
/source/{source_name}/database/{db}/collection/{col}/entity/{entity}
/source/{source_name}/database/{db}/collection/{col}/entity/{entity}/attribute/{attr}
/source/{source_name}/database/{db}/collection/{col}/relation/{relation}
```

The root key `$` holds top-level store metadata. All other keys are arbitrary strings — the JSONSource imposes no schema.

---

## Architecture

```
Claude / MCP client
        │  MCP (stdio transport)
        ▼
json_mcp.server   ← FastMCP app, 5 tool handlers
        │
json_mcp.config   ← singleton JSONSource factory
        │
        ▼
   JSONSource
   ├── MemoryJSONSource   ← BLUE_DATA_STORE=memory (default)
   └── FileJSONSource     ← BLUE_DATA_STORE=file
```

The server holds a single `JSONSource` instance per process. All tool calls
share that instance. With `BLUE_DATA_STORE=file`, state persists across server
restarts. With `BLUE_DATA_STORE=memory` (default), it is ephemeral.

---

## Running tests

```bash
cd platform/json-mcp
python3 -m pytest tests/ -v
```

Tests inject an in-memory store directly — no file I/O, no network required.
