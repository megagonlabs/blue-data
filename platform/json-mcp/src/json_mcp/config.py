"""JSONSource singleton factory — reads all config from environment variables.

See example.envrc at the repo root for the full list of supported variables.
"""
from __future__ import annotations

from typing import Optional

from blue_data.config import build_store
from blue_data.source.json.json_source import JSONSource

_store: Optional[JSONSource] = None


def get_store() -> JSONSource:
    global _store
    if _store is None:
        _store = build_store()
    return _store


def reset_store() -> None:
    """Replace the singleton with a fresh instance — for tests."""
    global _store
    _store = None
