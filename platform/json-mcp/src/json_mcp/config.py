"""JSONSource singleton factory.

Supports memory and file-based stores only (no Redis).

Environment variables:
    BLUE_DATA_STORE     memory (default) | file
    BLUE_DATA_FILE      path to JSON file (required when store=file)
"""
from __future__ import annotations

import os
from typing import Optional

from source.json.json_source import JSONSource
from source.json.memory_json_source import MemoryJSONSource

_store: Optional[JSONSource] = None


def get_store() -> JSONSource:
    global _store
    if _store is None:
        store_type = os.environ.get("BLUE_DATA_STORE", "memory").lower()
        if store_type == "file":
            from source.json.file_json_source import FileJSONSource
            path = os.environ.get("BLUE_DATA_FILE", "blue_data_store.json")
            _store = FileJSONSource(path)
        else:
            _store = MemoryJSONSource()
    return _store


def reset_store() -> None:
    global _store
    _store = None
