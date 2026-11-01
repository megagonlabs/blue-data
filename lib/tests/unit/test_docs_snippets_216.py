"""Regression guards for issue #216 (docs/snippets fail as written).

Covers the two parts verifiable without external services:
  1. lib/scripts/build.sh ships executable, like the platform build scripts
     (docs/installation.md tells the reader to run `./scripts/build.sh`); and
  2. the docs/guide.md enrichment snippet runs — it must register the source it
     operates on rather than calling collect_source_stats("sqlite") on an empty
     registry (which raised "Source not registered").

The platform/README path+command fixes, the RedisJSONSource constructor example and
the LangGraph demo's auth env are string/example fixes checked by hand.
"""
import os
import tempfile
from pathlib import Path

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

_BUILD_SH = Path(__file__).resolve().parents[2] / "scripts" / "build.sh"


def test_build_sh_is_executable():
    assert _BUILD_SH.is_file(), f"missing {_BUILD_SH}"
    assert os.access(_BUILD_SH, os.X_OK), "lib/scripts/build.sh must be executable (chmod +x)"


def test_guide_enrichment_snippet_runs():
    enricher = MetaData(llm_fn=None)
    registry = DataRegistry(store=MemoryJSONSource(), metadata_enricher=enricher)

    source = SQLiteDBSource("sqlite", properties={"connection": {"database_directory": tempfile.mkdtemp()}})
    registry.register_source(source)
    source.create_database("mydb")
    registry.execute_query(
        source="sqlite", database="mydb",
        query="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
        optional_properties={"commit": True},
    )

    registry.sync_source("sqlite", recursive=True)
    registry.collect_source_stats("sqlite", recursive=True)
    registry.enrich_source_metadata("sqlite", recursive=True, rebuild=False)

    # The source is registered and discoverable — the failure mode was a ValueError here.
    assert "sqlite" in registry.list_sources()
