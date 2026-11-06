"""blue-data registry MCP server.

Exposes DataRegistry operations as MCP tools so LLM clients (Claude Desktop,
Claude Code, etc.) can discover, explore, and enrich data assets.

Tool groups
-----------
Explore   — search_records, list_sources, list_source_databases,
            list_database_collections, list_collection_entities
Inspect   — get_entity, get_record
Manage    — sync_source, collect_source_stats, enrich_source,
            enrich_source_metadata
Query     — execute_query, import_data

Quick start
-----------
    # Install
    pip install -e ../../lib
    pip install -e .

    # Run (stdio transport for Claude Desktop / Claude Code)
    blue-data-registry-mcp

    # With a pre-loaded SQLite source
    BLUE_DATA_SOURCES_CONFIG=/path/to/config.json blue-data-registry-mcp

    # With Redis-backed persistent registry
    BLUE_DATA_REGISTRY_STORE=redis BLUE_DATA_REGISTRY_REDIS_URL=redis://localhost:6379/0 \\
        blue-data-registry-mcp

    # With LLM enrichment (Anthropic)
    BLUE_DATA_LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... \\
        blue-data-registry-mcp

Claude Desktop config (~/.config/claude-desktop/claude_desktop_config.json):
    {
      "mcpServers": {
        "blue-data-registry": {
          "command": "blue-data-registry-mcp",
          "env": {
            "BLUE_DATA_REGISTRY_STORE": "memory",
            "BLUE_DATA_SOURCES_CONFIG": "/path/to/sources.json"
          }
        }
      }
    }
"""
from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import os
import sys
import threading
from typing import Optional

from mcp.server.fastmcp import FastMCP

from registry_mcp.config import get_registry


# ---------------------------------------------------------------------------
# stdio transport isolation
# ---------------------------------------------------------------------------
# On a stdio MCP server, stdout carries JSON-RPC only. A hosted source (e.g. a user
# source that calls an LLM via LiteLLM) writes log lines to stdout, corrupting the
# protocol stream — and whether it does depends on which source ran first, because
# llm-source mutates the process-wide logger. Guard the transport boundary so only the
# JSON-RPC writer owns the real stdout; everything else goes to stderr (#282).

@contextlib.contextmanager
def _reserve_stdout_for_protocol():
    """Yield a text stream bound to the REAL stdout for the JSON-RPC protocol, and point
    the process stdout (fd 1) at stderr for the duration, so a hosted source's logging or
    stray prints can't reach the transport. Done at the fd level, so it also catches a
    logging handler that captured the original ``sys.stdout`` stream (#282)."""
    sys.stdout.flush()
    saved_stdout_fd = os.dup(1)   # to restore fd 1 afterwards
    protocol_fd = os.dup(1)       # the real stdout, reserved for JSON-RPC
    try:
        os.dup2(2, 1)             # fd 1 -> stderr: stray writes can't hit the protocol
        protocol = os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1, closefd=False)
        try:
            yield protocol
        finally:
            protocol.flush()
    finally:
        os.dup2(saved_stdout_fd, 1)
        os.close(saved_stdout_fd)
        os.close(protocol_fd)


def _quiet_litellm() -> None:
    """Raise embedded LiteLLM logging to WARNING so a hosted source's per-call INFO lines
    don't spam the stream. Defense-in-depth alongside the fd guard; no litellm import, so
    it is a no-op cost when no LLM source is hosted (#282)."""
    for name in ("LiteLLM", "litellm", "LiteLLM Proxy", "LiteLLM Router"):
        logging.getLogger(name).setLevel(logging.WARNING)


class IsolatedStdoutFastMCP(FastMCP):
    """FastMCP whose stdio transport reserves the real stdout for JSON-RPC (#282)."""

    async def run_stdio_async(self) -> None:
        import anyio
        from mcp.server.stdio import stdio_server

        try:
            cm = _reserve_stdout_for_protocol()
        except OSError:  # pragma: no cover - non-POSIX / no real stdout; fall back
            await super().run_stdio_async()
            return
        with cm as protocol:
            async with stdio_server(stdout=anyio.wrap_file(protocol)) as (read_stream, write_stream):
                await self._mcp_server.run(
                    read_stream,
                    write_stream,
                    self._mcp_server.create_initialization_options(),
                )


mcp = IsolatedStdoutFastMCP(
    "blue-data-registry",
    instructions=(
        "Data intelligence registry — discover, explore, and enrich data assets "
        "across heterogeneous sources (SQLite, Postgres, MongoDB, Neo4j, …)."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(e: Exception) -> str:
    return json.dumps({"error": str(e)}, indent=2)


# Writes are opt-in, matching the rest of the platform: read-only is the default on
# every surface (design/14 §3), and REST gates writes behind BLUE_DATA_API_ALLOW_WRITES.
# The MCP server exposes one write tool (import_data); it is refused unless this flag is
# set, so it can't overwrite a table the same session's execute_query would protect (#271).
# (env_flag lives in blue_data.server, which requires fastapi — not an MCP dep — so the
# one-liner is inlined here.)
_WRITE_FLAG = "BLUE_DATA_MCP_ALLOW_WRITES"


def _writes_allowed() -> bool:
    return os.environ.get(_WRITE_FLAG, "").lower() in ("1", "true", "yes")


def _tool(fn):
    """Register *fn* as an MCP tool whose body runs off the event loop.

    FastMCP 1.27 calls sync tools directly on its event loop; sibling sources
    that run their own ``asyncio.run`` (or refuse synchronous IO while a loop is
    running) then fail. When a loop is running the body is executed on a worker
    thread (which has no running loop); with no loop (e.g. unit tests calling
    the tool directly) it runs inline.
    """
    @mcp.tool()
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return fn(*args, **kwargs)

        box: dict = {}

        def _target():
            try:
                box["value"] = fn(*args, **kwargs)
            except BaseException as exc:  # re-raised on the calling thread
                box["error"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box["value"]

    return _wrapper


def _decode_query(query):
    """Decode a query that arrives as a JSON-object/array string into the
    native dict/list the source expects (doc, kb and web take dict ops).
    A plain SQL string is returned unchanged."""
    if isinstance(query, str):
        stripped = query.strip()
        if stripped[:1] in ("{", "["):
            try:
                return json.loads(stripped)
            except ValueError:
                return query
    return query


# ---------------------------------------------------------------------------
# Explore tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_records(
    query: str,
    record_type: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search registry records by keyword or semantic similarity.

    Returns ranked records with name, type, scope, description, and relevance
    score.  Use record_type to filter results to a specific kind of record.
    Use scope to restrict the search to a subtree of the registry.

    Args:
        query:       Natural-language search query.
        record_type: One of 'source', 'database', 'collection', 'entity',
                     'attribute', 'relation'.  Omit to search all types.
        scope:       Registry path prefix, e.g. '/source/mydb/database/sales'.
                     Omit to search the entire registry.
        limit:       Maximum number of results (default 10).
    """
    try:
        results = get_registry().search_records(
            query, type=record_type, scope=scope, page_size=limit
        )
        return _ok(results)
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_sources() -> str:
    """List the names of all registered data sources."""
    try:
        return _ok(get_registry().list_sources())
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_source_databases(source: str) -> str:
    """List all databases registered under a data source.

    Args:
        source: Name of the registered data source.
    """
    try:
        return _ok(get_registry().list_source_databases(source))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_database_collections(source: str, database: str) -> str:
    """List all collections (schemas) within a database.

    Args:
        source:   Name of the registered data source.
        database: Database name.
    """
    try:
        return _ok(get_registry().list_database_collections(source, database))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_collection_entities(source: str, database: str, collection: str) -> str:
    """List all entities (tables) within a collection.

    Args:
        source:     Name of the registered data source.
        database:   Database name.
        collection: Collection (schema) name — typically 'public' for SQL sources.
    """
    try:
        return _ok(get_registry().list_collection_entities(source, database, collection))
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Inspect tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_entity(source: str, database: str, collection: str, entity: str) -> str:
    """Get full details for an entity including all attributes and enrichment.

    Returns the entity record (description, stats, process_semantics,
    semantic_links) together with every attribute record enriched with
    value_semantics, semantic_role, quantitative_vst, and semantic_discovery
    where available.

    Args:
        source:     Name of the registered data source.
        database:   Database name.
        collection: Collection name (e.g. 'public').
        entity:     Entity (table) name.
    """
    try:
        registry = get_registry()
        record = registry.get_source_database_collection_entity(
            source, database, collection, entity
        )
        if record is None:
            return _err(ValueError(f"Entity '{entity}' not found"))

        attrs = registry.list_entity_attributes(source, database, collection, entity)
        enriched_attrs = []
        for attr in attrs:
            attr_name = attr["name"]
            enriched = dict(attr)
            for prop in (
                "value_semantics",
                "semantic_role",
                "quantitative_vst",
                "process_vst_role",
                "semantic_discovery",
                "domain_concept",
                "stats",
            ):
                val = registry.get_source_database_collection_entity_attribute_property(
                    source, database, collection, entity, attr_name, prop
                )
                if val is not None:
                    enriched[prop] = val
            enriched_attrs.append(enriched)

        return _ok({**record, "attributes": enriched_attrs})
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_record(name: str, record_type: str, scope: str) -> str:
    """Get a specific registry record by its (name, type, scope) identity.

    The scope follows the path convention:
        /source/{source}
        /source/{source}/database/{db}
        /source/{source}/database/{db}/collection/{col}
        /source/{source}/database/{db}/collection/{col}/entity/{entity}

    Args:
        name:        Record name.
        record_type: Record type ('source', 'database', 'collection', 'entity',
                     'attribute', 'relation').
        scope:       Full parent path (see above).
    """
    try:
        record = get_registry().get_record(name, record_type, scope)
        if record is None:
            return _err(
                ValueError(
                    f"Record '{name}' (type={record_type}, scope={scope}) not found"
                )
            )
        return _ok(record)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Manage tools
# ---------------------------------------------------------------------------

@_tool
def sync_source(source: str, recursive: bool = True) -> str:
    """Sync registry records from a live data source.

    Walks databases → collections → entities → attributes, reconciling
    the registry with what actually exists in the source.  Safe to call
    repeatedly (idempotent).  The source must already be registered.

    Args:
        source:    Name of the registered data source.
        recursive: Descend through all levels (default True).
    """
    try:
        get_registry().sync_source(source, recursive=recursive)
        return _ok({"status": "ok", "source": source, "recursive": recursive})
    except Exception as e:
        return _err(e)


@_tool
def collect_source_stats(source: str, recursive: bool = True) -> str:
    """Collect statistics from a live data source into the registry.

    Gathers row counts, sample values, min/max, distinct counts, and null
    counts at every level (database → collection → entity → attribute).
    Required before running enrichment.

    Args:
        source:    Name of the registered data source.
        recursive: Collect stats at all levels (default True).
    """
    try:
        get_registry().collect_source_stats(source, recursive=recursive)
        return _ok({"status": "ok", "source": source})
    except Exception as e:
        return _err(e)


@_tool
def enrich_source(source: str) -> str:
    """Run deterministic semantic type inference on all attributes in a source.

    Detects INTEGER, FLOAT, DATE, EMAIL, ENUM_CATEGORY, FREE_TEXT, UUID, etc.
    Writes results to attribute.properties['value_semantics'].
    Requires collect_source_stats to have run first.

    Args:
        source: Name of the registered data source.
    """
    try:
        get_registry().enrich_source(source)
        return _ok({"status": "ok", "source": source})
    except Exception as e:
        return _err(e)


@_tool
def enrich_source_metadata(
    source: str, recursive: bool = True, rebuild: bool = False
) -> str:
    """Run the full MetaData enrichment pipeline on a source.

    Adds semantic roles, quantitative VST classifications, process semantics,
    semantic links between attributes, and — if the server was started with
    BLUE_DATA_LLM_PROVIDER set — LLM-augmented enrichments (value semantics
    inference, semantic discovery, and entity descriptions).

    rebuild=False (default) is idempotent: existing properties are preserved.
    rebuild=True forces re-enrichment of everything, including LLM properties.

    Requires collect_source_stats to have run first.

    Args:
        source:    Name of the registered data source.
        recursive: Enrich all levels (default True).
        rebuild:   Overwrite already-enriched properties (default False).
    """
    try:
        get_registry().enrich_source_metadata(
            source, recursive=recursive, rebuild=rebuild
        )
        return _ok({"status": "ok", "source": source, "rebuild": rebuild})
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Query tools
# ---------------------------------------------------------------------------

@_tool
def execute_query(
    source: str,
    query: str,
    database: Optional[str] = None,
    collection: Optional[str] = None,
) -> str:
    """Execute a native query against a registered data source and return rows.

    For SQL sources (SQLite, Postgres, MySQL) pass a SQL SELECT statement.
    For sources that take JSON ops (doc, kb, web) pass the op as a JSON object
    string, e.g. '{"op": "DOCUMENT.SEARCH", "query": "..."}' — it is decoded to
    the dict the source expects. Results are returned as a JSON array of rows.

    Args:
        source:     Name of the registered data source.
        query:      Native query — a SQL string, or a JSON-object string for
                    sources that take dict ops.
        database:   Database name (required for SQL sources).
        collection: Collection / schema name (optional).
    """
    try:
        rows = get_registry().execute_query(
            source, _decode_query(query), database=database, collection=collection
        )
        return _ok(rows)
    except Exception as e:
        return _err(e)


@_tool
def import_data(
    source: str,
    target: str,
    database: str = "default",
    collection: str = "default",
    entity: Optional[str] = None,
    mode: str = "append",
) -> str:
    """Import rows from one registered data source into another.

    Reads data from *source* (using *collection* as the table/file name) and
    writes it to *target*.  SQL targets (SQLite, Postgres, MySQL) require
    *entity* (destination table name).

    This is a **write** operation and is disabled by default (read-only is the
    platform default). Start the MCP server with ``BLUE_DATA_MCP_ALLOW_WRITES=true``
    to allow it; otherwise it is refused, like a write via execute_query (#271).

    Args:
        source:     Name of the registered source data source (data origin).
        target:     Name of the registered target data source (data destination).
        collection: Collection / table / file name to read from the source.
        database:   Database name on the target (default 'default').
        entity:     Destination table name on the target (required for SQL targets).
        mode:       'append' (default) adds rows; 'overwrite' clears the target first.
    """
    if not _writes_allowed():
        return _err(PermissionError(
            "import_data is a write operation and is disabled by default. Start the MCP "
            f"server with {_WRITE_FLAG}=true to allow writes."
        ))
    try:
        result = get_registry().import_data(
            source=source,
            target=target,
            collection=collection,
            database=database,
            entity=entity,
            mode=mode,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _quiet_litellm()
    mcp.run()


if __name__ == "__main__":
    main()
