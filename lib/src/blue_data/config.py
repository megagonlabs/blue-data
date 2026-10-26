"""Shared environment-variable reader for all platform components.

All configuration is read from environment variables documented in example.envrc.
Each platform component's config.py imports from here rather than duplicating
this logic.
"""
from __future__ import annotations

import json
import os


def _getenv_float(key: str, default: float) -> float:
    try:
        return float(os.environ[key])
    except (KeyError, ValueError):
        return default


def _getenv_int(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


def _getenv_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


def build_store():
    """Build a JSONSource from env vars."""
    store_type = os.environ.get("BLUE_DATA_REGISTRY_STORE", "memory").lower()

    if store_type == "redis":
        import urllib.parse
        from blue_data.source.json.redis.redis_json_source import RedisJSONSource
        url = os.environ.get("BLUE_DATA_REGISTRY_REDIS_URL", "redis://localhost:6379/0")
        namespace = os.environ.get("BLUE_DATA_REGISTRY_REDIS_NAMESPACE", "blue_data")
        parsed = urllib.parse.urlparse(url)
        return RedisJSONSource(properties={
            "namespace": namespace,
            "connection": {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 6379,
                "db": int((parsed.path or "/0").lstrip("/") or "0"),
            },
        })

    if store_type == "file":
        from blue_data.source.json.file_json_source import FileJSONSource
        path = os.environ.get("BLUE_DATA_REGISTRY_FILE", "blue_data_store.json")
        return FileJSONSource(properties={"connection": {"path": path}})

    from blue_data.source.json.memory_json_source import MemoryJSONSource
    return MemoryJSONSource()


def build_hybrid_config() -> dict:
    """Build HybridSearch config from env vars."""
    config = {}

    bm25_weight = _getenv_float("BLUE_DATA_REGISTRY_SEARCH_BM25_WEIGHT", -1)
    if bm25_weight >= 0:
        config["bm25_weight"] = bm25_weight

    vector_weight = _getenv_float("BLUE_DATA_REGISTRY_SEARCH_VECTOR_WEIGHT", -1)
    if vector_weight >= 0:
        config["vector_weight"] = vector_weight

    value_weight = _getenv_float("BLUE_DATA_REGISTRY_SEARCH_VALUE_WEIGHT", -1)
    if value_weight >= 0:
        config["value_weight"] = value_weight

    bm25_threshold = os.environ.get("BLUE_DATA_REGISTRY_SEARCH_BM25_THRESHOLD")
    if bm25_threshold is not None:
        try:
            config["bm25_threshold"] = float(bm25_threshold)
        except ValueError:
            pass

    vector_threshold = os.environ.get("BLUE_DATA_REGISTRY_SEARCH_VECTOR_THRESHOLD")
    if vector_threshold is not None:
        try:
            config["vector_threshold"] = float(vector_threshold)
        except ValueError:
            pass

    combined_threshold = os.environ.get("BLUE_DATA_REGISTRY_SEARCH_COMBINED_THRESHOLD")
    if combined_threshold is not None:
        try:
            config["combined_threshold"] = float(combined_threshold)
        except ValueError:
            pass

    hierarchical = os.environ.get("BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL")
    if hierarchical is not None:
        config["hierarchical_enabled"] = hierarchical.lower() in ("1", "true", "yes")

    return config or None


def get_vector_dim() -> int:
    return _getenv_int("BLUE_DATA_REGISTRY_VECTOR_DIM", 1536)


def build_enricher():
    """Build a MetaData enricher from env vars."""
    from blue_data.registry.enrichment.metadata import MetaData

    provider = os.environ.get("BLUE_DATA_LLM_PROVIDER", "").lower()

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                # Resolve the model after the provider: an empty/unset BLUE_DATA_LLM_MODEL
                # must fall through to the Anthropic default, not a cross-provider value
                # (e.g. the family default gpt-4o exported by the CLI). #101
                model = (
                    os.environ.get("BLUE_DATA_REGISTRY_METADATA_LLM_MODEL")
                    or os.environ.get("BLUE_DATA_LLM_MODEL")
                    or "claude-opus-4-8"
                )
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
                # Resolve the model after the provider (#101): empty/unset falls
                # through to the OpenAI default rather than a cross-provider value.
                model = (
                    os.environ.get("BLUE_DATA_REGISTRY_METADATA_LLM_MODEL")
                    or os.environ.get("BLUE_DATA_LLM_MODEL")
                    or "gpt-4o"
                )
                client = openai.OpenAI(api_key=api_key)

                def llm_fn(prompt: str) -> str:
                    resp = client.chat.completions.create(
                        model=model, max_completion_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return resp.choices[0].message.content or ""

                return MetaData(llm_fn=llm_fn)
            except ImportError:
                pass

    return MetaData(llm_fn=None)


def load_sources(registry) -> None:
    """Pre-load data sources from BLUE_DATA_SOURCES_CONFIG JSON file into registry."""
    path = os.environ.get("BLUE_DATA_SOURCES_CONFIG")
    if not path or not os.path.exists(path):
        return

    with open(path) as f:
        cfg = json.load(f)

    sync = _getenv_bool("BLUE_DATA_SOURCES_SYNC", True)

    for src in cfg.get("sources", []):
        src_type = src.get("type", "").lower()
        name = src.get("name")
        props = src.get("properties", {})

        if src_type == "sqlite":
            from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
            registry.register_source(SQLiteDBSource(name=name, properties=props))
        elif src_type == "postgres":
            from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource
            registry.register_source(PostgresDBSource(name=name, properties=props))
        elif src_type == "mysql":
            from blue_data.source.sql.mysql.mysql_sql_source import MySQLDBSource
            registry.register_source(MySQLDBSource(name=name, properties=props))
        elif src_type == "mongodb":
            from blue_data.source.json.mongodb.mongodb_json_source import MongoDBSource
            registry.register_source(MongoDBSource(name=name, properties=props))
        elif src_type == "class":
            # Any DataSource subclass, incl. sibling sources (doc/kb/llm/user/web),
            # instantiated from its fully-qualified path: {"type": "class",
            # "_class": "pkg.mod.Cls", "properties": {...}}.
            class_path = src.get("_class") or props.get("_class")
            if not class_path:
                continue
            from blue_data.source.source import DataSource
            registry.register_source(DataSource.instantiate(class_path, name, properties=props))
        else:
            continue

        if sync and name:
            registry.sync_source(name, recursive=True)
