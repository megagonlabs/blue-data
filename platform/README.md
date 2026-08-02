# Platform

The `platform/` directory contains deployable components built on top of `lib/`. Install `lib` first — all components depend on it.

| Component | Description | Docs |
|---|---|---|
| `registry-mcp` | MCP server — exposes registry operations as tools for Claude and other MCP clients | [docs/registry-mcp.md](../docs/registry-mcp.md) |
| `api` | REST API (FastAPI) with interactive docs at `/docs` | [docs/api.md](../docs/api.md) |
| `cli` | Command-line interface for the full pipeline (register → sync → stats → enrich → search) | [docs/cli.md](../docs/cli.md) |
| `json-mcp` | MCP server for raw JSONSource operations (memory + file backends) | [docs/json-mcp.md](../docs/json-mcp.md) |

## Installation

Each component has a `scripts/install.sh` for editable installs. Run from the component's root:

```bash
pip install -e ../lib        # always install lib first

cd registry-mcp && pip install -e .
cd api && pip install -e .
cd cli && pip install -e .
cd json-mcp && pip install -e .
```

## Quick start

**registry-mcp** (stdio transport — for Claude Desktop / Claude Code):
```bash
blue-data-registry-mcp
```

**api** (dev server):
```bash
blue-data-api  # http://localhost:8000 · interactive docs at /docs
```

**cli**:
```bash
blue-data sources add mydb --type sqlite --database-dir /data
blue-data sync mydb
blue-data search "revenue"
```

**json-mcp**:
```bash
blue-data-json-mcp
```

## Configuration

All components share the same environment variables. See the [Configuration section](../README.md#configuration) in the root README for the full reference.
