from __future__ import annotations

from typing import Any

from blue_data.core.stores.json_store import JSONStore


class MemoryJSONStore(JSONStore):
    """In-memory JSON storage backend for local/dev/test use."""

    def __init__(self):
        self.data: dict[str, Any] = {}

    def get(self, path: str | None = None) -> Any:
        if path in (None, "", "$"):
            return self.data
        return self.data.get(path)

    def set(self, path: str | None, value: Any) -> None:
        if path in (None, "", "$"):
            self.data = value
        else:
            self.data[path] = value

    def delete(self, path: str | None = None) -> None:
        if path in (None, "", "$"):
            self.data = {}
        else:
            self.data.pop(path, None)