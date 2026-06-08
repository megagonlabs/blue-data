from __future__ import annotations

from typing import Any

from source.json.json_source import JSONSource


class RedisJSONSource(JSONSource):
    """Redis-backed JSON storage backend.

    This is the production-compatible backend for Blue-style registry/state storage.
    Full RedisJSON implementation will wrap existing Blue redis_source.py behavior.
    """

    def __init__(self, connection: Any = None, properties: dict | None = None):
        self.connection = connection
        self.properties = properties or {}

    def get(self, path: str | None = None) -> Any:
        raise NotImplementedError("RedisJSONSource.get is not implemented yet")

    def set(self, path: str | None, value: Any) -> None:
        raise NotImplementedError("RedisJSONSource.set is not implemented yet")

    def delete(self, path: str | None = None) -> None:
        raise NotImplementedError("RedisJSONSource.delete is not implemented yet")