"""Registry singleton factory — reads all config from environment variables.

See example.envrc at the repo root for the full list of supported variables.
"""
from __future__ import annotations

from typing import Optional

from blue_data.config import (
    build_store,
    build_enricher,
    build_embedding_fn,
    build_vector_source,
    build_hybrid_config,
    get_vector_dim,
    load_sources,
)
from blue_data.registry.data_registry import DataRegistry

_registry: Optional[DataRegistry] = None


def get_registry() -> DataRegistry:
    global _registry
    if _registry is None:
        embedding_fn = build_embedding_fn()
        vector_source = build_vector_source(embedding_fn)
        _registry = DataRegistry(
            store=build_store(),
            vector_source=vector_source,
            embedding_fn=embedding_fn,
            metadata_enricher=build_enricher(),
            hybrid_config=build_hybrid_config(),
            vector_dim=get_vector_dim(),
            rebuild=vector_source is not None,
        )
        load_sources(_registry)
    return _registry


def reset_registry() -> None:
    """Replace the singleton with a fresh instance — for tests."""
    global _registry
    _registry = None
