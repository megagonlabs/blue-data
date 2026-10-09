"""blue-registry CLI.

Usage:
    blue-registry [OPTIONS] COMMAND [ARGS]...

Global options:
    --profile  Configuration profile (default: the selected one in ~/.blue-registry)
    --format   Output format: table (default), json, or nl
    --store    Override BLUE_DATA_REGISTRY_STORE (memory|redis|file)
    --config   Override BLUE_DATA_SOURCES_CONFIG path

Commands:
    profile  Manage profiles and configuration
    source   Manage and operate on registered data sources
    search   Search registry records
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click

from registry_cli.config import get_registry, reset_registry
from registry_cli.profile import _cli_home, profile_group, profile_store, resolver_for


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data, fmt: str) -> None:
    if fmt == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    elif fmt == "nl":
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    click.echo(item.get("name", str(item)))
                else:
                    click.echo(str(item))
        elif isinstance(data, dict):
            click.echo(data.get("name", str(data)))
        else:
            click.echo(str(data))
    else:  # table
        if isinstance(data, list):
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


def _status(msg: str, fmt: str) -> None:
    click.echo(msg, err=(fmt == "json"))


def _err(code: str, msg: str) -> None:
    click.echo(f"ERROR: {code} {msg}", err=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="blue-registry-cli", prog_name="blue-registry")
@click.option("--profile", "profile_name",
              envvar="BLUE_DATA_PROFILE", default=None,
              help="Configuration profile. Overrides BLUE_DATA_PROFILE. "
                   "Defaults to the selection in ~/.blue-registry/.selected.profile.")
@click.option("--format", "fmt",
              type=click.Choice(["table", "json", "nl"]),
              default=None, show_default=True,
              help="Output format (table, json, or nl). Overrides BLUE_DATA_CLI_FORMAT.")
@click.option("--store", envvar="BLUE_DATA_REGISTRY_STORE", default=None,
              help="Registry backend (memory, file, or redis). Overrides BLUE_DATA_REGISTRY_STORE.")
@click.option("--config", "config_path", envvar="BLUE_DATA_SOURCES_CONFIG", default=None,
              help="Path to sources config JSON file. Overrides BLUE_DATA_SOURCES_CONFIG.")
@click.pass_context
def cli(ctx: click.Context, profile_name: Optional[str], fmt: Optional[str],
        store: Optional[str], config_path: Optional[str]):
    """blue-registry — inspect and manage your data registry."""
    home = _cli_home()

    # A fresh install gets its `default` profile on first command rather than
    # requiring `blue-registry profile add` before anything works.
    profile_store(home).initialize()

    # Apply the profile: resolved values are written into the environment so the
    # library, env-var-aware options, and downstream config readers all see them.
    # Command-line flags (--store, --config) applied below take precedence.
    resolver = resolver_for(home, profile_name)
    resolver.export()

    # Explicit CLI flags override the profile-exported values.
    if store:
        os.environ["BLUE_DATA_REGISTRY_STORE"] = store
    if config_path:
        os.environ["BLUE_DATA_SOURCES_CONFIG"] = config_path

    # fmt: command flag > profile BLUE_DATA_CLI_FORMAT > default "table"
    effective_fmt = fmt or resolver.get("BLUE_DATA_CLI_FORMAT") or "table"

    ctx.ensure_object(dict)
    ctx.obj["fmt"]     = effective_fmt
    ctx.obj["home"]    = home
    ctx.obj["profile"] = resolver.profile
    ctx.obj["config"]  = resolver
    ctx.obj["registry"] = get_registry()


cli.add_command(profile_group)


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
    fmt = ctx.obj["fmt"]
    records = reg.list_records(record_type="source", scope="/")
    if fmt == "json":
        click.echo(json.dumps([r["name"] for r in records]))
    elif fmt == "nl":
        for record in records:
            click.echo(record["name"])
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
@click.option("--host", default="localhost", show_default=True, help="Postgres host.")
@click.option("--port", default=5432, type=int, show_default=True, help="Postgres port.")
@click.option("--db-name", default=None, help="Postgres database name.")
@click.option("--user", default=None, help="Postgres user.")
@click.pass_context
def source_add(ctx: click.Context, name: str, src_type: str, database_dir: Optional[str],
               host: str, port: int, db_name: Optional[str], user: Optional[str]):
    """Register a new data source.

    Password is read from the BLUE_REGISTRY_SOURCE_PASSWORD environment variable.

    \b
    Examples:
      blue-registry source add mydb --type sqlite --database-dir /data/sqlite
      BLUE_REGISTRY_SOURCE_PASSWORD=secret blue-registry source add prod --type postgres --host localhost --db-name mydb --user app
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
                    "database": db_name, "user": user,
                    "password": os.environ.get("BLUE_REGISTRY_SOURCE_PASSWORD"),
                }},
            )
        reg.register_source(src)
        _status(f"Registered source '{name}' ({src_type}).", ctx.obj["fmt"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation prompt.")
@click.pass_context
def source_remove(ctx: click.Context, name: str, yes: bool):
    """Deregister a source."""
    reg = ctx.obj["registry"]
    if reg.get_source_record(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    if not yes:
        click.confirm(f"Remove source '{name}' from the registry?", abort=True)
    reg.deregister_source(name)
    _status(f"Removed source '{name}'.", ctx.obj["fmt"])


@source.command("sync")
@click.argument("name")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def source_sync(ctx: click.Context, name: str, no_recursive: bool):
    """Sync registry records from the live source."""
    reg = ctx.obj["registry"]
    if reg.connect_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.sync_source(name, recursive=not no_recursive)
        _status(f"Synced '{name}'.", ctx.obj["fmt"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("stats")
@click.argument("name")
@click.option("--no-recursive", is_flag=True, default=False)
@click.pass_context
def source_stats(ctx: click.Context, name: str, no_recursive: bool):
    """Collect statistics from the live source."""
    reg = ctx.obj["registry"]
    if reg.connect_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.collect_source_stats(name, recursive=not no_recursive)
        _status(f"Stats collected for '{name}'.", ctx.obj["fmt"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("enrich")
@click.argument("name")
@click.pass_context
def source_enrich(ctx: click.Context, name: str):
    """Run semantic type inference on all attributes."""
    reg = ctx.obj["registry"]
    if reg.connect_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        reg.enrich_source(name)
        _status(f"Enriched '{name}'.", ctx.obj["fmt"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


@source.command("metadata")
@click.argument("name")
@click.option("--rebuild", is_flag=True, default=False, help="Overwrite existing enrichment.")
@click.pass_context
def source_metadata(ctx: click.Context, name: str, rebuild: bool):
    """Run the full MetaData enrichment pipeline."""
    import sys
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

    reg = ctx.obj["registry"]
    fmt = ctx.obj["fmt"]
    if reg.connect_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        if fmt == "json" or not sys.stderr.isatty():
            reg.enrich_source_metadata(name, recursive=True, rebuild=rebuild)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task("Enriching…", total=None)

                def on_progress(entity_name, database, collection, done, total):
                    progress.update(task, total=total, completed=done,
                                    description=f"[bold]{entity_name}[/bold]")

                reg.enrich_source_metadata(name, recursive=True, rebuild=rebuild,
                                           on_progress=on_progress)
        _status(f"Metadata enrichment complete for '{name}'.", fmt)
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
    if reg.connect_source(name) is None:
        _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
    try:
        results = reg.execute_query(
            name, sql, database=database, optional_properties={"commit": True}
        )
        _out(results or [], ctx.obj["fmt"])
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
    fmt = ctx.obj["fmt"]

    if attribute is not None:
        record = reg.get_source_database_collection_entity_attribute(
            name, database, collection, entity, attribute
        )
        if record is None:
            _err("RECORD_NOT_FOUND", f"Attribute '{attribute}' not found.")
        if fmt == "json":
            click.echo(json.dumps({"record": record}, indent=2, default=str))
        else:
            props = record.get("properties") or {}
            info = props.get("info") or {}
            sql_type = info.get("type", "")
            sem = props.get("semantic_type", "")
            click.echo(_fmt_record(record))
            if sql_type:
                click.echo(f"  sql_type: {sql_type}")
            if sem:
                click.echo(f"  semantic_type: {sem}")

    elif entity is not None:
        record = reg.get_source_database_collection_entity(name, database, collection, entity)
        if record is None:
            _err("RECORD_NOT_FOUND", f"Entity '{entity}' not found.")
        attributes = reg.list_entity_attributes(name, database, collection, entity)
        if fmt == "json":
            click.echo(json.dumps({"record": record, "attributes": attributes}, indent=2, default=str))
        else:
            click.echo(_fmt_record(record))
            click.echo("  attributes:")
            for attr in attributes:
                props = attr.get("properties") or {}
                sem = props.get("semantic_type", "")
                sql_type = (props.get("info") or {}).get("type", "")
                tag = sem or sql_type
                suffix = f"  [{tag}]" if tag else ""
                click.echo(f"    {attr['name']}{suffix}")

    elif collection is not None:
        record = reg.get_source_database_collection(name, database, collection)
        if record is None:
            _err("RECORD_NOT_FOUND", f"Collection '{collection}' not found.")
        entities = reg.list_collection_entities(name, database, collection)
        relations = reg.list_collection_relations(name, database, collection)
        if fmt == "json":
            # Strip the raw schema string — it duplicates the entities/relations lists.
            rec = {k: v for k, v in record.items() if k != "properties"}
            rec["properties"] = {k: v for k, v in (record.get("properties") or {}).items()
                                  if k != "schema"}
            click.echo(json.dumps(
                {"record": rec, "entities": entities, "relations": relations},
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
        if fmt == "json":
            click.echo(json.dumps({"record": record, "collections": cols}, indent=2, default=str))
        else:
            click.echo(_fmt_record(record))
            click.echo(f"  collections: {', '.join(c['name'] for c in cols) if cols else '(none)'}")

    else:
        record = reg.get_source_record(name)
        if record is None:
            _err("SOURCE_NOT_FOUND", f"Source '{name}' not found.")
        dbs = reg.list_source_databases(name)
        if fmt == "json":
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
@click.option("--top-k", "limit", default=10, show_default=True, help="Maximum results to return.")
@click.pass_context
def search(ctx: click.Context, query: str, record_type: Optional[str], limit: int):
    """Search records using hybrid BM25 + vector search."""
    reg = ctx.obj["registry"]
    try:
        results = reg.search_records(query, type=record_type, page_size=limit)
        _out(results, ctx.obj["fmt"])
    except Exception as e:
        _err("COMMAND_FAILED", str(e))


if __name__ == "__main__":
    cli()
