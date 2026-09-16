# MCP Servers

blue-data ships two MCP servers. Choose based on what you need to do.

---

## Which server to use

| | `registry-mcp` | `json-mcp` |
|---|---|---|
| **Use when** | You want an LLM to explore data sources, search the catalog, run enrichment, or issue natural-language queries | You want direct key/value access to the raw registry store for inspection or manual edits |
| **Exposes** | `DataRegistry` — full source hierarchy, search, enrichment, stats | `JSONSource` — raw `get`/`set`/`delete`/`list_keys` on the underlying store |
| **Persistence** | Memory (default) or Redis (`BLUE_DATA_REGISTRY_STORE=redis`) | Memory (default) or file (`BLUE_DATA_REGISTRY_STORE=file`) |
| **LLM enrichment** | Optional (`BLUE_DATA_LLM_PROVIDER=anthropic\|openai`) | Not available |
| **Package** | `platform/registry-mcp` | `platform/json-mcp` |

In most cases, start with `registry-mcp`. Use `json-mcp` when you need to inspect or patch the registry state at the storage level without going through `DataRegistry`.

---

## registry-mcp

Full documentation: **[registry-mcp.md](registry-mcp.md)**

```bash
cd platform/registry-mcp
pip install -e ../../lib -e .

# Start with a pre-loaded source config
BLUE_DATA_SOURCES_CONFIG=/path/to/sources.json blue-data-registry-mcp
```

Claude Desktop config (`~/.config/claude-desktop/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "blue-data-registry": {
      "command": "blue-data-registry-mcp",
      "env": {
        "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json"
      }
    }
  }
}
```

Tools available: `search_records`, `list_sources`, `list_source_databases`, `list_database_collections`, `list_collection_entities`, `get_entity`, `get_record`, `sync_source`, `collect_source_stats`, `enrich_source`, `enrich_source_metadata`.

---

## json-mcp

Full documentation: **[json-mcp.md](json-mcp.md)**

```bash
cd platform/json-mcp
pip install -e ../../lib -e .

# Start with a persistent file-backed store
BLUE_DATA_REGISTRY_STORE=file BLUE_DATA_REGISTRY_FILE=/path/to/store.json blue-data-json-mcp
```

Claude Desktop config:

```json
{
  "mcpServers": {
    "blue-data-json": {
      "command": "blue-data-json-mcp",
      "env": {
        "BLUE_DATA_REGISTRY_STORE": "file",
        "BLUE_DATA_REGISTRY_FILE": "/path/to/store.json"
      }
    }
  }
}
```

Tools available: `json_get`, `json_set`, `json_delete`, `json_list_keys`, `json_get_all`.

---

## Running both servers together

The two servers are independent processes. You can run both simultaneously if you need an LLM to both operate the registry and inspect raw storage:

```json
{
  "mcpServers": {
    "blue-data-registry": {
      "command": "blue-data-registry-mcp",
      "env": { "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json" }
    },
    "blue-data-json": {
      "command": "blue-data-json-mcp",
      "env": { "BLUE_DATA_REGISTRY_STORE": "memory" }
    }
  }
}
```

Each server holds its own independent store instance.
