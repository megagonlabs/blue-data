from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from blue_data.core.utils.file_lock import file_lock, write_json_atomic
from blue_data.core.utils.json_utils import json_query_delete, json_query_get, json_query_set
from blue_data.source.json.json_source import JSONSource


class FileJSONSource(JSONSource):
    """File-backed JSON storage backend."""

    def __init__(self, name: str = "file_json", properties: dict | None = None):
        super().__init__(name, properties=properties)
        self.path = self.properties["connection"]["path"]
        if not os.path.exists(self.path):
            self._ensure_parent()
            with file_lock(self.path):
                if not os.path.exists(self.path):
                    self._write({})

    def _initialize_connection_properties(self) -> None:
        conn = self.properties.get("connection", {})
        conn.setdefault("protocol", "json/file")
        conn.setdefault("path", "registry.json")
        self.properties["connection"] = conn

    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else {}

    def _ensure_parent(self) -> None:
        parent = Path(self.path).parent
        parent_existed = parent.exists()
        parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            try:
                os.chmod(parent, 0o700)
            except PermissionError:
                pass

    def _write(self, data: dict) -> None:
        """Atomically replace the file; callers that read first must hold file_lock(self.path)."""
        self._ensure_parent()
        write_json_atomic(self.path, data, mode=0o600, indent=2, ensure_ascii=False)

    def get(self, path: str | None = None) -> Any:
        data = self._read()
        if path in (None, "", "$"):
            return data
        return json_query_get(data, path)

    def set(self, path: str | None, value: Any) -> None:
        with file_lock(self.path):
            data = self._read()
            if path in (None, "", "$"):
                data = value
            else:
                json_query_set(data, path, value)
            self._write(data)

    def delete(self, path: str | None = None) -> None:
        with file_lock(self.path):
            data = self._read()
            if path in (None, "", "$"):
                data = {}
            else:
                json_query_delete(data, path)
            self._write(data)

    # ---------- DataSource interface ----------

    def fetch_databases(self) -> list[str]:
        return ["default"]

    def fetch_database_collections(self, database: str) -> list[str]:
        data = self._read()
        return list(data.keys()) if isinstance(data, dict) else []

    def fetch_source_stats(self) -> dict:
        data = self._read()
        return {"total_keys": len(data) if isinstance(data, dict) else 0}
