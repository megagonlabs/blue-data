"""Registry singleton factory — same env-var contract as registry-mcp.

    BLUE_DATA_STORE             memory (default) | redis
    BLUE_DATA_REDIS_URL         redis://localhost:6379/0
    BLUE_DATA_REDIS_NAMESPACE   blue_data (default)
    BLUE_DATA_LLM_PROVIDER      anthropic | openai
    BLUE_DATA_LLM_MODEL         claude-opus-4-8 (default for anthropic) | gpt-4o (default for openai)
    ANTHROPIC_API_KEY           required when LLM_PROVIDER=anthropic
    OPENAI_API_KEY              required when LLM_PROVIDER=openai
    BLUE_DATA_CONFIG            path to JSON source-config file
"""
from __future__ import annotations

import json
import os
from typing import Optional

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.enrichment.metadata import MetaData
from blue_data.source.json.memory_json_source import MemoryJSONSource

_registry: Optional[DataRegistry] = None


def _build_store():
    if os.environ.get("BLUE_DATA_STORE", "memory").lower() == "redis":
        import urllib.parse
        from blue_data.source.json.redis.redis_json_source import RedisJSONSource
        url = os.environ.get("BLUE_DATA_REDIS_URL", "redis://localhost:6379/0")
        ns  = os.environ.get("BLUE_DATA_REDIS_NAMESPACE", "blue_data")
        p   = urllib.parse.urlparse(url)
        return RedisJSONSource(properties={
            "namespace": ns,
            "connection": {
                "host": p.hostname or "localhost",
                "port": p.port or 6379,
                "db":   int((p.path or "/0").lstrip("/") or "0"),
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
                model  = os.environ.get("BLUE_DATA_LLM_MODEL", "claude-opus-4-8")
                client = anthropic.Anthropic(api_key=api_key)

                def llm_fn(prompt: str) -> str:
                    resp = client.messages.create(
                        model=model, max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    for block in resp.content:
                        if block.type == "text":
                            return block.text
                    return ""

                return MetaData(llm_fn=llm_fn)
            except ImportError:
                pass
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                import openai
                model  = os.environ.get("BLUE_DATA_LLM_MODEL", "gpt-4o")
                client = openai.OpenAI(api_key=api_key)

                def llm_fn(prompt: str) -> str:
                    response = client.chat.completions.create(
                        model=model, max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return response.choices[0].message.content or ""

                return MetaData(llm_fn=llm_fn)
            except ImportError:
                pass
    return MetaData(llm_fn=None)


def _load_sources(registry: DataRegistry) -> None:
    path = os.environ.get("BLUE_DATA_CONFIG")
    if not path or not os.path.exists(path):
        return
    with open(path) as f:
        cfg = json.load(f)
    for src in cfg.get("sources", []):
        t, name, props = src.get("type", "").lower(), src.get("name"), src.get("properties", {})
        if t == "sqlite":
            from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
            registry.register_source(SQLiteDBSource(name=name, properties=props))
        elif t == "postgres":
            from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource
            registry.register_source(PostgresDBSource(name=name, properties=props))
        elif t == "mysql":
            from blue_data.source.sql.mysql.mysql_sql_source import MySQLDBSource
            registry.register_source(MySQLDBSource(name=name, properties=props))
        elif t == "mongodb":
            from blue_data.source.json.mongodb.mongodb_json_source import MongoDBJSONSource
            registry.register_source(MongoDBJSONSource(name=name, properties=props))


def get_registry() -> DataRegistry:
    global _registry
    if _registry is None:
        _registry = DataRegistry(store=_build_store(), metadata_enricher=_build_enricher())
        _load_sources(_registry)
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
