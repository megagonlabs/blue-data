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

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from registry_mcp.config import get_registry

mcp = FastMCP(
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

@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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

@mcp.tool()
def execute_query(
    source: str,
    query: str,
    database: Optional[str] = None,
    collection: Optional[str] = None,
) -> str:
    """Execute a native query against a registered data source and return rows.

    For SQL sources (SQLite, Postgres, MySQL) pass a SQL SELECT statement.
    Results are returned as a JSON array of row objects.

    Args:
        source:     Name of the registered data source.
        query:      Native query string (e.g. SQL SELECT statement).
        database:   Database name (required for SQL sources).
        collection: Collection / schema name (optional).
    """
    try:
        rows = get_registry().execute_query(
            source, query, database=database, collection=collection
        )
        return _ok(rows)
    except Exception as e:
        return _err(e)


@mcp.tool()
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

    Args:
        source:     Name of the registered source data source (data origin).
        target:     Name of the registered target data source (data destination).
        collection: Collection / table / file name to read from the source.
        database:   Database name on the target (default 'default').
        entity:     Destination table name on the target (required for SQL targets).
        mode:       'append' (default) adds rows; 'overwrite' clears the target first.
    """
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
    mcp.run()


if __name__ == "__main__":
    main()
