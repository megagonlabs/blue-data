"""blue-data CLI.

Usage:
    blue-data [OPTIONS] COMMAND [ARGS]...

Global options:
    --json    Output raw JSON instead of formatted text
    --store   Override BLUE_DATA_STORE (memory|redis)
    --config  Override BLUE_DATA_CONFIG path

Commands mirror the three platform components: sources, operations, search,
and hierarchy inspection.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click

from registry_cli.config import get_registry, reset_registry


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                click.echo(_fmt_record(item))
            else:
                click.echo(str(item))
    elif isinstance(data, dict):
        click.echo(_fmt_record(data))
    else:
        click.echo(str(data))


def _fmt_record(r: dict) -> str:
    parts = [f"{r.get('type', '?')}  {r.get('name', '?')}"]
    if r.get("description"):
        parts.append(f"  {r['description']}")
    if r.get("properties"):
        props = r["properties"]
        if "semantic_type" in props:
            parts.append(f"  semantic_type: {props['semantic_type']}")
        if "stats" in props:
            s = props["stats"]
            stat_line = "  stats: " + "  ".join(
                f"{k}={v}" for k, v in s.items() if v is not None
            )
            parts.append(stat_line)
    return "\n".join(parts)


def _err(msg: str) -> None:
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--json", "as_json", is_flag=True, default=False, help="Output raw JSON.")
@click.option("--store", envvar="BLUE_DATA_STORE", default=None, help="memory or redis.")
@click.option("--config", "config_path", envvar="BLUE_DATA_CONFIG", default=None,
              help="Path to source config JSON file.")
@click.pass_context
def cli(ctx: click.Context, as_json: bool, store: Optional[str], config_path: Optional[str]):
    """blue-data — inspect and manage your data registry."""
    ctx.ensure_object(dict)
    ctx.obj["as_json"] = as_json
    if store:
        os.environ["BLUE_DATA_STORE"] = store
    if config_path:
        os.environ["BLUE_DATA_CONFIG"] = config_path
    ctx.obj["registry"] = get_registry()


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

@cli.group()
def sources():
    """Manage registered data sources."""


@sources.command("list")
@click.pass_context
def sources_list(ctx: click.Context):
    """List all registered sources."""
    reg = ctx.obj["registry"]
    names = reg.list_sources()
    if ctx.obj["as_json"]:
        click.echo(json.dumps(names))
    else:
        if not names:
            click.echo("No sources registered.")
        for name in names:
            record = reg.get_source_record(name)
            click.echo(f"  {name}" + (f"  — {record.get('description', '')}" if record else ""))


@sources.command("add")
@click.argument("name")
@click.option("--type", "src_type", required=True,
              type=click.Choice(["sqlite", "postgres"]),
              help="Source type.")
@click.option("--database-dir", default=None, help="SQLite database directory.")
@click.option("--host", default="localhost", help="Postgres host.")
@click.option("--port", default=5432, type=int, help="Postgres port.")
@click.option("--dbname", default=None, help="Postgres database name.")
@click.option("--user", default=None, help="Postgres user.")
@click.option("--password", default=None, help="Postgres password.")
@click.pass_context
def sources_add(ctx: click.Context, name: str, src_type: str, database_dir: Optional[str],
                host: str, port: int, dbname: Optional[str], user: Optional[str],
                password: Optional[str]):
    """Register a new data source."""
    reg = ctx.obj["registry"]
    try:
        if src_type == "sqlite":
            from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
            src = SQLiteDBSource(
                name=name,
                properties={"connection": {"database_directory": database_dir or "."}},
            )
        elif src_type == "postgres":
            from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource
            src = PostgresDBSource(
                name=name,
                properties={"connection": {
                    "host": host, "port": port,
                    "database": dbname, "user": user, "password": password,
                }},
            )
        reg.register_source(src)
        click.echo(f"Registered source '{name}' ({src_type}).")
    except Exception as e:
        _err(str(e))


@sources.command("remove")
@click.argument("name")
@click.pass_context
def sources_remove(ctx: click.Context, name: str):
    """Deregister a source."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err(f"Source '{name}' not found.")
    reg.deregister_source(name)
    click.echo(f"Removed source '{name}'.")


# ---------------------------------------------------------------------------
# sync / stats / enrich / metadata
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("source")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def sync(ctx: click.Context, source: str, no_recursive: bool):
    """Sync registry records from the live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(source) is None:
        _err(f"Source '{source}' not found.")
    try:
        reg.sync_source(source, recursive=not no_recursive)
        click.echo(f"Synced '{source}'.")
    except Exception as e:
        _err(str(e))


@cli.command()
@click.argument("source")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def stats(ctx: click.Context, source: str, no_recursive: bool):
    """Collect statistics from the live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(source) is None:
        _err(f"Source '{source}' not found.")
    try:
        reg.collect_source_stats(source, recursive=not no_recursive)
        click.echo(f"Stats collected for '{source}'.")
    except Exception as e:
        _err(str(e))


@cli.command()
@click.argument("source")
@click.pass_context
def enrich(ctx: click.Context, source: str):
    """Run semantic type inference on all attributes."""
    reg = ctx.obj["registry"]
    if reg.get_source(source) is None:
        _err(f"Source '{source}' not found.")
    try:
        reg.enrich_source(source)
        click.echo(f"Enriched '{source}'.")
    except Exception as e:
        _err(str(e))


@cli.command()
@click.argument("source")
@click.option("--rebuild", is_flag=True, default=False, help="Overwrite existing enrichment.")
@click.pass_context
def metadata(ctx: click.Context, source: str, rebuild: bool):
    """Run the full MetaData enrichment pipeline."""
    reg = ctx.obj["registry"]
    if reg.get_source(source) is None:
        _err(f"Source '{source}' not found.")
    try:
        reg.enrich_source_metadata(source, recursive=True, rebuild=rebuild)
        click.echo(f"Metadata enrichment complete for '{source}'.")
    except Exception as e:
        _err(str(e))


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("--type", "record_type", default=None, help="Filter by record type.")
@click.option("--limit", default=10, show_default=True, help="Max results.")
@click.pass_context
def search(ctx: click.Context, query: str, record_type: Optional[str], limit: int):
    """Search records using hybrid BM25 + vector search."""
    reg = ctx.obj["registry"]
    try:
        results = reg.search_records(query, type=record_type, page_size=limit)
    except Exception as e:
        _err(str(e))
    _out(results, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

@cli.group()
def inspect():
    """Inspect registry records at any hierarchy level."""


@inspect.command("source")
@click.argument("name")
@click.pass_context
def inspect_source(ctx: click.Context, name: str):
    """Show source record and its databases."""
    reg = ctx.obj["registry"]
    record = reg.get_source_record(name)
    if record is None:
        _err(f"Source '{name}' not found.")
    dbs = reg.list_source_databases(name)
    if ctx.obj["as_json"]:
        click.echo(json.dumps({"record": record, "databases": dbs}, indent=2, default=str))
    else:
        click.echo(_fmt_record(record))
        click.echo(f"  databases: {', '.join(d['name'] for d in dbs) if dbs else '(none)'}")


@inspect.command("database")
@click.argument("source")
@click.argument("database")
@click.pass_context
def inspect_database(ctx: click.Context, source: str, database: str):
    """Show database record and its collections."""
    reg = ctx.obj["registry"]
    record = reg.get_source_database(source, database)
    if record is None:
        _err(f"Database '{database}' not found under source '{source}'.")
    cols = reg.list_database_collections(source, database)
    if ctx.obj["as_json"]:
        click.echo(json.dumps({"record": record, "collections": cols}, indent=2, default=str))
    else:
        click.echo(_fmt_record(record))
        click.echo(f"  collections: {', '.join(c['name'] for c in cols) if cols else '(none)'}")


@inspect.command("collection")
@click.argument("source")
@click.argument("database")
@click.argument("collection")
@click.pass_context
def inspect_collection(ctx: click.Context, source: str, database: str, collection: str):
    """Show collection record, entities, and relations."""
    reg = ctx.obj["registry"]
    record = reg.get_source_database_collection(source, database, collection)
    if record is None:
        _err(f"Collection '{collection}' not found.")
    entities = reg.list_collection_entities(source, database, collection)
    relations = reg.list_collection_relations(source, database, collection)
    if ctx.obj["as_json"]:
        click.echo(json.dumps(
            {"record": record, "entities": entities, "relations": relations},
            indent=2, default=str,
        ))
    else:
        click.echo(_fmt_record(record))
        click.echo(f"  entities:  {', '.join(e['name'] for e in entities) if entities else '(none)'}")
        click.echo(f"  relations: {', '.join(r['name'] for r in relations) if relations else '(none)'}")


@inspect.command("entity")
@click.argument("source")
@click.argument("database")
@click.argument("collection")
@click.argument("entity")
@click.pass_context
def inspect_entity(ctx: click.Context, source: str, database: str, collection: str, entity: str):
    """Show entity record and its attributes."""
    reg = ctx.obj["registry"]
    record = reg.get_source_database_collection_entity(source, database, collection, entity)
    if record is None:
        _err(f"Entity '{entity}' not found.")
    attributes = reg.list_entity_attributes(source, database, collection, entity)
    if ctx.obj["as_json"]:
        click.echo(json.dumps({"record": record, "attributes": attributes}, indent=2, default=str))
    else:
        click.echo(_fmt_record(record))
        click.echo("  attributes:")
        for attr in attributes:
            sem = (attr.get("properties") or {}).get("semantic_type", "")
            suffix = f"  [{sem}]" if sem else ""
            click.echo(f"    {attr['name']}{suffix}")


@inspect.command("attribute")
@click.argument("source")
@click.argument("database")
@click.argument("collection")
@click.argument("entity")
@click.argument("attribute")
@click.pass_context
def inspect_attribute(ctx: click.Context, source: str, database: str, collection: str,
                      entity: str, attribute: str):
    """Show a single attribute record with all enrichment properties."""
    reg = ctx.obj["registry"]
    record = reg.get_source_database_collection_entity_attribute(
        source, database, collection, entity, attribute
    )
    if record is None:
        _err(f"Attribute '{attribute}' not found.")
    _out(record, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("source")
@click.argument("sql")
@click.option("--database", default=None, help="Target database.")
@click.pass_context
def query(ctx: click.Context, source: str, sql: str, database: Optional[str]):
    """Execute a SQL query against a live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(source) is None:
        _err(f"Source '{source}' not found.")
    try:
        results = reg.execute_query(
            source, sql, database=database, optional_properties={"commit": True}
        )
        _out(results or [], ctx.obj["as_json"])
    except Exception as e:
        _err(str(e))


if __name__ == "__main__":
    cli()
