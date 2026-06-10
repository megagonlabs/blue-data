from __future__ import annotations

import copy
import logging
from typing import Any

import redis

from source.json.json_source import JSONSource


class RedisJSONSource(JSONSource):
    """Redis-backed JSON storage for the Registry.

    Stores each registry path as a separate Redis key prefixed by namespace.
    Mirrors the flat-dict interface of MemoryJSONSource.
    """

    def __init__(self, connection: Any = None, properties: dict | None = None):
        self.properties = properties or {}
        self.logger = logging.getLogger(self.__class__.__name__)

        if connection is not None:
            self.connection = connection
        else:
            self._initialize_connection_properties()
            self.connection = self._connect()

        self._namespace = self.properties.get("namespace", "registry")

    # ---------- connection ----------

    def _initialize_connection_properties(self):
        conn = self.properties.get("connection", {})
        conn.setdefault("host", "localhost")
        conn.setdefault("port", 6379)
        conn.setdefault("db", 0)
        self.properties["connection"] = conn

    def _connect(self):
        conn = self.properties.get("connection", {})
        config = copy.deepcopy(conn)
        config.pop("protocol", None)
        config.pop("subprotocol", None)
        return redis.Redis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=config.get("password"),
            decode_responses=True,
        )

    # ---------- key helpers ----------

    def _key(self, path: str) -> str:
        return f"{self._namespace}:{path}"

    def _path_from_key(self, key: str) -> str:
        prefix = f"{self._namespace}:"
        return key[len(prefix):]

    # ---------- JSONSource interface ----------

    def get(self, path: str | None = None) -> Any:
        if path in (None, ""):
            path = "$"
        key = self._key(path)
        try:
            result = self.connection.json().get(key, "$")
            if isinstance(result, list) and len(result) == 1:
                return result[0]
            return result
        except Exception:
            return None

    def set(self, path: str | None, value: Any) -> None:
        if path in (None, ""):
            path = "$"
        key = self._key(path)
        self.connection.json().set(key, "$", value)

    def delete(self, path: str | None = None) -> None:
        if path in (None, ""):
            path = "$"
        key = self._key(path)
        self.connection.delete(key)

    # ---------- data property (needed by Registry.list_records etc.) ----------

    @property
    def data(self) -> dict[str, Any]:
        """SCAN-backed snapshot of all stored paths → values.

        Mirrors MemoryJSONSource.data so Registry can iterate all records.
        """
        pattern = f"{self._namespace}:*"
        prefix = f"{self._namespace}:"
        result: dict[str, Any] = {}
        cursor = 0

        while True:
            cursor, keys = self.connection.scan(
                cursor=cursor, match=pattern, count=500
            )
            for key in keys:
                if not isinstance(key, str):
                    continue
                path = key[len(prefix):]
                try:
                    doc = self.connection.json().get(key, "$")
                    if isinstance(doc, list) and len(doc) == 1:
                        result[path] = doc[0]
                    elif doc is not None:
                        result[path] = doc
                except Exception:
                    pass

            if cursor == 0:
                break

        return result
