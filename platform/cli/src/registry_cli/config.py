"""Registry singleton factory — reads all config from environment variables.

See .env.example at the repo root for the full list of supported variables.
"""
from __future__ import annotations

from typing import Optional

from blue_data.config import build_store, build_enricher, build_hybrid_config, get_vector_dim, load_sources
from blue_data.registry.data_registry import DataRegistry

_registry: Optional[DataRegistry] = None


def get_registry() -> DataRegistry:
    global _registry
    if _registry is None:
        _registry = DataRegistry(
            store=build_store(),
            metadata_enricher=build_enricher(),
            hybrid_config=build_hybrid_config(),
            vector_dim=get_vector_dim(),
        )
        load_sources(_registry)
    return _registry


def reset_registry() -> None:
    """Replace the singleton with a fresh instance — for tests."""
    global _registry
    _registry = None
