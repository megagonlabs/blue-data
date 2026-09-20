"""blue-registry CLI.

Usage:
    blue-registry [OPTIONS] COMMAND [ARGS]...

Global options:
    --json    Output raw JSON instead of formatted text
    --store   Override BLUE_DATA_REGISTRY_STORE (memory|redis)
    --config  Override BLUE_DATA_SOURCES_CONFIG path

Commands:
    source  Manage and operate on registered data sources
    search  Search registry records
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


def _err(code: str, msg: str) -> None:
    click.echo(f"ERROR: {code} {msg}", err=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="blue-registry-cli", prog_name="blue-registry")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output raw JSON.")
@click.option("--store", envvar="BLUE_DATA_REGISTRY_STORE", default=None, help="memory or redis.")
@click.option("--config", "config_path", envvar="BLUE_DATA_SOURCES_CONFIG", default=None,
              help="Path to source config JSON file.")
@click.pass_context
def cli(ctx: click.Context, as_json: bool, store: Optional[str], config_path: Optional[str]):
    """blue-registry — inspect and manage your data registry."""
    ctx.ensure_object(dict)
    ctx.obj["as_json"] = as_json
    if store:
        os.environ["BLUE_DATA_REGISTRY_STORE"] = store
    if config_path:
        os.environ["BLUE_DATA_SOURCES_CONFIG"] = config_path
    ctx.obj["registry"] = get_registry()


# ---------------------------------------------------------------------------
# source group
# ---------------------------------------------------------------------------

@cli.group()
def source():
    """Manage and operate on registered data sources."""


@source.command("list")
@click.pass_context
def source_list(ctx: click.Context):
    """List all registered sources."""
    reg = ctx.obj["registry"]
    records = reg.list_records(record_type="source", scope="/")
    if ctx.obj["as_json"]:
        click.echo(json.dumps([r["name"] for r in records]))
    else:
        if not records:
            click.echo("No sources registered.")
        for record in records:
            click.echo(f"  {record['name']}" + (f"  — {record.get('description', '')}" if record.get('description') else ""))


@source.command("add")
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
def source_add(ctx: click.Context, name: str, src_type: str, database_dir: Optional[str],
               host: str, port: int, dbname: Optional[str], user: Optional[str],
               password: Optional[str]):
    """Register a new data source.

    \b
    Examples:
      blue-registry source add mydb --type sqlite --database-dir /data/sqlite
      blue-registry source add prod --type postgres --host localhost --dbname mydb --user app
    """
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
        _err("COMMAND_FAILED", str(e))


@source.command("remove")
@click.argument("name")
@click.pass_context
def source_remove(ctx: click.Context, name: str):
    """Deregister a source."""
    reg = ctx.obj["registry"]
    if reg.get_source_record(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    reg.deregister_source(name)
    click.echo(f"Removed source '{name}'.")


@source.command("sync")
@click.argument("name")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def source_sync(ctx: click.Context, name: str, no_recursive: bool):
    """Sync registry records from the live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.sync_source(name, recursive=not no_recursive)
        click.echo(f"Synced '{name}'.")
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("stats")
@click.argument("name")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def source_stats(ctx: click.Context, name: str, no_recursive: bool):
    """Collect statistics from the live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.collect_source_stats(name, recursive=not no_recursive)
        click.echo(f"Stats collected for '{name}'.")
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("enrich")
@click.argument("name")
@click.pass_context
def source_enrich(ctx: click.Context, name: str):
    """Run semantic type inference on all attributes."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.enrich_source(name)
        click.echo(f"Enriched '{name}'.")
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("metadata")
@click.argument("name")
@click.option("--rebuild", is_flag=True, default=False, help="Overwrite existing enrichment.")
@click.pass_context
def source_metadata(ctx: click.Context, name: str, rebuild: bool):
    """Run the full MetaData enrichment pipeline."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.enrich_source_metadata(name, recursive=True, rebuild=rebuild)
        click.echo(f"Metadata enrichment complete for '{name}'.")
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("query")
@click.argument("name")
@click.argument("sql")
@click.option("--database", default=None, help="Target database.")
@click.pass_context
def source_query(ctx: click.Context, name: str, sql: str, database: Optional[str]):
    """Execute a SQL query against a live source."""
    reg = ctx.obj["registry"]
    if reg.get_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        results = reg.execute_query(
            name, sql, database=database, optional_properties={"commit": True}
        )
        _out(results or [], ctx.obj["as_json"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("inspect")
@click.argument("name")
@click.argument("database", required=False, default=None)
@click.argument("collection", required=False, default=None)
@click.argument("entity", required=False, default=None)
@click.argument("attribute", required=False, default=None)
@click.pass_context
def source_inspect(ctx: click.Context, name: str, database: Optional[str],
                   collection: Optional[str], entity: Optional[str],
                   attribute: Optional[str]):
    """Inspect a source, database, collection, entity, or attribute.

    \b
    Examples:
      blue-registry source inspect mydb
      blue-registry source inspect mydb prod
      blue-registry source inspect mydb prod public
      blue-registry source inspect mydb prod public orders
      blue-registry source inspect mydb prod public orders total
    """
    reg = ctx.obj["registry"]
    as_json = ctx.obj["as_json"]

    if attribute is not None:
        record = reg.get_source_database_collection_entity_attribute(
            name, database, collection, entity, attribute
        )
        if record is None:
            _err("RECORD_NOT_FOUND", f"Attribute '{attribute}' not found.")
        _out(record, as_json)

    elif entity is not None:
        record = reg.get_source_database_collection_entity(name, database, collection, entity)
        if record is None:
            _err("RECORD_NOT_FOUND", f"Entity '{entity}' not found.")
        attributes = reg.list_entity_attributes(name, database, collection, entity)
        if as_json:
            click.echo(json.dumps({"record": record, "attributes": attributes}, indent=2, default=str))
        else:
            click.echo(_fmt_record(record))
            click.echo("  attributes:")
            for attr in attributes:
                sem = (attr.get("properties") or {}).get("semantic_type", "")
                suffix = f"  [{sem}]" if sem else ""
                click.echo(f"    {attr['name']}{suffix}")

    elif collection is not None:
        record = reg.get_source_database_collection(name, database, collection)
        if record is None:
            _err("RECORD_NOT_FOUND", f"Collection '{collection}' not found.")
        entities = reg.list_collection_entities(name, database, collection)
        relations = reg.list_collection_relations(name, database, collection)
        if as_json:
            click.echo(json.dumps(
                {"record": record, "entities": entities, "relations": relations},
                indent=2, default=str,
            ))
        else:
            click.echo(_fmt_record(record))
            click.echo(f"  entities:  {', '.join(e['name'] for e in entities) if entities else '(none)'}")
            click.echo(f"  relations: {', '.join(r['name'] for r in relations) if relations else '(none)'}")

    elif database is not None:
        record = reg.get_source_database(name, database)
        if record is None:
            _err("RECORD_NOT_FOUND", f"Database '{database}' not found under source '{name}'.")
        cols = reg.list_database_collections(name, database)
        if as_json:
            click.echo(json.dumps({"record": record, "collections": cols}, indent=2, default=str))
        else:
            click.echo(_fmt_record(record))
            click.echo(f"  collections: {', '.join(c['name'] for c in cols) if cols else '(none)'}")

    else:
        record = reg.get_source_record(name)
        if record is None:
            _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
        dbs = reg.list_source_databases(name)
        if as_json:
            click.echo(json.dumps({"record": record, "databases": dbs}, indent=2, default=str))
        else:
            click.echo(_fmt_record(record))
            click.echo(f"  databases: {', '.join(d['name'] for d in dbs) if dbs else '(none)'}")


# ---------------------------------------------------------------------------
# search (top-level — not source-scoped)
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
        _out(results, ctx.obj["as_json"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


if __name__ == "__main__":
    cli()
