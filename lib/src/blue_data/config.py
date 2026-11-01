"""Shared environment-variable reader for all platform components.

All configuration is read from environment variables documented in example.envrc.
Each platform component's config.py imports from here rather than duplicating
this logic.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# Built-in source types -> fully-qualified class path (instantiated via DataSource).
_SOURCE_TYPE_CLASSES = {
    "sqlite": "blue_data.source.sql.sqlite.sqlite_sql_source.SQLiteDBSource",
    "postgres": "blue_data.source.sql.postgres.postgres_sql_source.PostgresDBSource",
    "mysql": "blue_data.source.sql.mysql.mysql_sql_source.MySQLDBSource",
    "mongodb": "blue_data.source.json.mongodb.mongodb_json_source.MongoDBSource",
}


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


def _redis_connection_from_url(url: str) -> dict:
    """Parse a Redis URL into a connection dict that preserves full credentials.

    Carries the whole ``url`` so the source's ``_connect`` can authenticate via
    ``redis.Redis.from_url`` — keeping the username, password, the ``rediss://`` TLS
    scheme and any query options the URL sets. host/port/db are also parsed for
    inspection, and username/ssl are surfaced as discrete keys. The password stays in
    the URL only (the credential sanitiser strips URI userinfo before persisting, so a
    registered data source never stores it). #211"""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    conn = {
        "url": url,
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "db": int((parsed.path or "/0").lstrip("/") or "0"),
    }
    if parsed.username:
        conn["username"] = urllib.parse.unquote(parsed.username)
    if parsed.scheme == "rediss":
        conn["ssl"] = True
    return conn


def build_store():
    """Build a JSONSource from env vars."""
    store_type = os.environ.get("BLUE_DATA_REGISTRY_STORE", "memory").lower()

    if store_type == "redis":
        from blue_data.source.json.redis.redis_json_source import RedisJSONSource
        url = os.environ.get("BLUE_DATA_REGISTRY_REDIS_URL", "redis://localhost:6379/0")
        namespace = os.environ.get("BLUE_DATA_REGISTRY_REDIS_NAMESPACE", "blue_data")
        return RedisJSONSource(properties={
            "namespace": namespace,
            "connection": _redis_connection_from_url(url),
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


def build_embedding_fn():
    """Build an embedding function from env vars, or None when no embedding provider
    is configured — in which case registry search runs keyword/BM25-only. #108

    Configure with BLUE_DATA_EMBEDDING_PROVIDER=openai (+ OPENAI_API_KEY) and,
    optionally, BLUE_DATA_EMBEDDING_MODEL (default text-embedding-3-small)."""
    provider = os.environ.get("BLUE_DATA_EMBEDDING_PROVIDER", "").lower()
    if not provider:
        return None

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "BLUE_DATA_EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set; "
                "embeddings are disabled and registry search falls back to keyword-only."
            )
            return None
        try:
            import openai
        except ImportError:
            logger.warning(
                "BLUE_DATA_EMBEDDING_PROVIDER=openai but the 'openai' package is not installed "
                "(pip install 'blue-data[llm]'); embeddings are disabled (keyword-only search)."
            )
            return None
        model = os.environ.get("BLUE_DATA_EMBEDDING_MODEL", "text-embedding-3-small")
        client = openai.OpenAI(api_key=api_key)

        def embedding_fn(text: str) -> list[float]:
            resp = client.embeddings.create(model=model, input=text)
            return resp.data[0].embedding

        return embedding_fn

    logger.warning(
        "Unknown BLUE_DATA_EMBEDDING_PROVIDER=%r (expected 'openai'); embeddings are disabled.",
        provider,
    )
    return None


def build_vector_source(embedding_fn=None):
    """Build a VectorSource from env vars so the platforms get real hybrid search. #108

    Returns None when *embedding_fn* is None — vector search needs embeddings, so
    without a provider the registry stays keyword-only rather than wiring a dead
    vector source.

    The vector store defaults to match the registry store's durability, so the
    embeddings a sync pays for outlive the command exactly when the registry record
    does: a ``redis`` store gets RedisVectorSource, a ``file`` store gets a
    FileVectorSource beside the registry file, and a ``memory`` store gets
    MemoryVectorSource. Otherwise a single-shot CLI command would embed every record
    (billed) into an in-memory store discarded at process exit, and the next search
    would find no vectors (#213). BLUE_DATA_REGISTRY_VECTOR_SOURCE overrides the default
    (memory | file | redis)."""
    if embedding_fn is None:
        return None

    store_type = os.environ.get("BLUE_DATA_REGISTRY_STORE", "memory").lower()
    default_vs = {"redis": "redis", "file": "file"}.get(store_type, "memory")
    vs_type = os.environ.get("BLUE_DATA_REGISTRY_VECTOR_SOURCE", default_vs).lower()

    if vs_type == "redis":
        from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource
        url = os.environ.get("BLUE_DATA_REGISTRY_REDIS_URL", "redis://localhost:6379/0")
        scan_prefix = os.environ.get("BLUE_DATA_REGISTRY_VECTOR_SCAN_PREFIX", "blue_data_vec:")
        connection = _redis_connection_from_url(url)
        # RediSearch (FT.CREATE) only builds indexes on db 0. Rather than fail the whole
        # registry (the JSON store may legitimately run on db != 0), disable vector search
        # with a loud warning so the degradation to keyword-only is visible, not silent. #215
        if connection.get("db", 0) != 0:
            logger.warning(
                "BLUE_DATA_REGISTRY_VECTOR_SOURCE=redis on db %s: RediSearch creates indexes "
                "only on db 0, so vector search is disabled (registry search is keyword-only). "
                "Point BLUE_DATA_REGISTRY_REDIS_URL at db 0 and isolate tenants with "
                "BLUE_DATA_REGISTRY_VECTOR_SCAN_PREFIX.",
                connection.get("db"),
            )
            return None
        connection["scan_prefix"] = scan_prefix
        return RedisVectorSource(name="registry_vectors", properties={
            "connection": connection,
        })

    if vs_type == "file":
        from blue_data.source.vector.file_vector_source import FileVectorSource
        directory = os.environ.get("BLUE_DATA_REGISTRY_VECTOR_DIR")
        if not directory:
            # Default beside the registry file so the vectors sit next to the store
            # they index (both survive the command).
            reg_file = os.environ.get("BLUE_DATA_REGISTRY_FILE", "blue_data_store.json")
            directory = os.path.join(os.path.dirname(os.path.abspath(reg_file)), "vectors")
        return FileVectorSource(name="registry_vectors", directory=directory)

    if store_type != "memory":
        logger.warning(
            "BLUE_DATA_REGISTRY_VECTOR_SOURCE=memory with a %s registry store: embeddings "
            "computed at sync time are discarded when the process exits, so search falls "
            "back to keyword-only. Set it to 'file' or 'redis' to persist vectors.",
            store_type,
        )

    from blue_data.source.vector.memory_vector_source import MemoryVectorSource
    return MemoryVectorSource(name="registry_vectors")


def build_enricher():
    """Build a MetaData enricher from env vars."""
    from blue_data.registry.enrichment.metadata import MetaData

    provider = os.environ.get("BLUE_DATA_LLM_PROVIDER", "").lower()
    if not provider:
        return MetaData(llm_fn=None)

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "BLUE_DATA_LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set; "
                "metadata enrichment is disabled."
            )
            return MetaData(llm_fn=None)
        try:
            import anthropic
        except ImportError:
            logger.warning(
                "BLUE_DATA_LLM_PROVIDER=anthropic but the 'anthropic' package is not installed "
                "(pip install 'blue-data[llm]'); metadata enrichment is disabled."
            )
            return MetaData(llm_fn=None)
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

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "BLUE_DATA_LLM_PROVIDER=openai but OPENAI_API_KEY is not set; "
                "metadata enrichment is disabled."
            )
            return MetaData(llm_fn=None)
        try:
            import openai
        except ImportError:
            logger.warning(
                "BLUE_DATA_LLM_PROVIDER=openai but the 'openai' package is not installed "
                "(pip install 'blue-data[llm]'); metadata enrichment is disabled."
            )
            return MetaData(llm_fn=None)
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

    logger.warning(
        "Unknown BLUE_DATA_LLM_PROVIDER=%r (expected 'anthropic' or 'openai'); "
        "metadata enrichment is disabled.",
        provider,
    )
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

        class_path = _SOURCE_TYPE_CLASSES.get(src_type)
        if src_type == "class":
            # Any DataSource subclass, incl. sibling sources (doc/kb/llm/user/web),
            # from its fully-qualified path: {"type": "class", "_class": "pkg.mod.Cls", ...}.
            class_path = src.get("_class") or props.get("_class")
        if not class_path or not name:
            continue

        # Isolate per-source failures: a source connects eagerly at construction, so one
        # unreachable configured source must not abort get_registry() and take down every
        # tool. Register it as unavailable and continue. #106
        from blue_data.source.source import DataSource
        try:
            registry.register_source(DataSource.instantiate(class_path, name, properties=props))
        except Exception as e:
            logger.warning("Failed to load source %r (%s): %s", name, class_path, e)
            try:
                registry.register_unavailable_source(name, class_path, props, e)
            except Exception:
                logger.warning("Could not register placeholder record for source %r", name)
            continue

        if sync:
            try:
                registry.sync_source(name, recursive=True)
            except Exception as e:
                logger.warning("Failed to sync source %r: %s", name, e)
