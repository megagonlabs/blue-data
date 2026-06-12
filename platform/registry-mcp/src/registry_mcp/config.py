"""Registry singleton factory.

The registry instance is created once per process from environment variables:

    BLUE_DATA_STORE             memory (default) | redis
    BLUE_DATA_REDIS_URL         redis://localhost:6379/0
    BLUE_DATA_REDIS_NAMESPACE   blue_data (default)

    BLUE_DATA_LLM_PROVIDER      anthropic (optional — enables LLM enrichment)
    BLUE_DATA_LLM_MODEL         claude-opus-4-8 (default when LLM enabled)
    ANTHROPIC_API_KEY           required when LLM_PROVIDER=anthropic

    BLUE_DATA_CONFIG            path to JSON file pre-loading data sources (optional)

Config file format:
    {
      "sources": [
        {
          "type": "sqlite",
          "name": "mydb",
          "properties": {"connection": {"database_directory": "/data/dbs"}}
        }
      ]
    }
"""
from __future__ import annotations

import json
import os
from typing import Optional

from registry.data_registry import DataRegistry
from registry.enrichment.metadata import MetaData
from source.json.memory_json_source import MemoryJSONSource

_registry: Optional[DataRegistry] = None


def _build_store():
    store_type = os.environ.get("BLUE_DATA_STORE", "memory").lower()
    if store_type == "redis":
        from source.json.redis.redis_json_source import RedisJSONSource
        import urllib.parse
        url = os.environ.get("BLUE_DATA_REDIS_URL", "redis://localhost:6379/0")
        namespace = os.environ.get("BLUE_DATA_REDIS_NAMESPACE", "blue_data")
        parsed = urllib.parse.urlparse(url)
        return RedisJSONSource(properties={
            "namespace": namespace,
            "connection": {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 6379,
                "db": int((parsed.path or "/0").lstrip("/") or "0"),
            },
        })
    return MemoryJSONSource()


def _build_enricher() -> MetaData:
    provider = os.environ.get("BLUE_DATA_LLM_PROVIDER", "").lower()
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                model = os.environ.get("BLUE_DATA_LLM_MODEL", "claude-opus-4-8")
                client = anthropic.Anthropic(api_key=api_key)

                def llm_fn(prompt: str) -> str:
                    response = client.messages.create(
                        model=model,
                        max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    for block in response.content:
                        if block.type == "text":
                            return block.text
                    return ""

                return MetaData(llm_fn=llm_fn)
            except ImportError:
                pass
    return MetaData(llm_fn=None)


def _load_sources(registry: DataRegistry) -> None:
    config_path = os.environ.get("BLUE_DATA_CONFIG")
    if not config_path or not os.path.exists(config_path):
        return

    with open(config_path) as f:
        config = json.load(f)

    for src_cfg in config.get("sources", []):
        src_type = src_cfg.get("type", "").lower()
        name = src_cfg.get("name")
        properties = src_cfg.get("properties", {})

        if src_type == "sqlite":
            from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
            registry.register_source(SQLiteDBSource(name=name, properties=properties))
        elif src_type == "postgres":
            from source.sql.postgres.postgres_sql_source import PostgresDBSource
            registry.register_source(PostgresDBSource(name=name, properties=properties))
        elif src_type == "mysql":
            from source.sql.mysql.mysql_sql_source import MySQLDBSource
            registry.register_source(MySQLDBSource(name=name, properties=properties))
        elif src_type == "mongodb":
            from source.json.mongodb.mongodb_json_source import MongoDBJSONSource
            registry.register_source(MongoDBJSONSource(name=name, properties=properties))


def get_registry() -> DataRegistry:
    global _registry
    if _registry is None:
        _registry = DataRegistry(
            store=_build_store(),
            metadata_enricher=_build_enricher(),
        )
        _load_sources(_registry)
    return _registry


def reset_registry() -> None:
    """Replace the singleton with a fresh instance — for tests."""
    global _registry
    _registry = None
