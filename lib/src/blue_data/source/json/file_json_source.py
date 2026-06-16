from __future__ import annotations

import json
import os
from typing import Any

from blue_data.source.json.json_source import JSONSource


class FileJSONSource(JSONSource):
    """File-backed JSON storage backend."""

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            self._write({})

    def _read(self) -> dict:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, path: str | None = None) -> Any:
        data = self._read()
        if path in (None, "", "$"):
            return data
        return data.get(path)

    def set(self, path: str | None, value: Any) -> None:
        data = self._read()
        if path in (None, "", "$"):
            data = value
        else:
            data[path] = value
        self._write(data)

    def delete(self, path: str | None = None) -> None:
        data = self._read()
        if path in (None, "", "$"):
            data = {}
        else:
            data.pop(path, None)
        self._write(data)
