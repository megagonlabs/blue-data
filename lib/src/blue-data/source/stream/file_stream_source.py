from __future__ import annotations

import json
import os

from source.stream.stream_source import StreamSource


class FileStreamSource(StreamSource):
    """File-backed stream source — appends JSON lines to per-stream files."""

    def __init__(self, name: str, directory: str = ".", properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._directory = os.path.abspath(directory)
        os.makedirs(self._directory, exist_ok=True)
        self._cursors: dict[str, int] = {}

    def _stream_path(self, stream: str) -> str:
        return os.path.join(self._directory, stream + ".jsonl")

    def publish(self, stream: str, message: dict) -> None:
        with open(self._stream_path(stream), "a") as f:
            f.write(json.dumps(message) + "\n")

    def consume(self, stream: str, count: int = 1) -> list[dict]:
        path = self._stream_path(stream)
        if not os.path.exists(path):
            return []
        with open(path) as f:
            lines = f.readlines()
        cursor = self._cursors.get(stream, 0)
        batch = lines[cursor: cursor + count]
        self._cursors[stream] = cursor + len(batch)
        return [json.loads(line) for line in batch]

    def acknowledge(self, stream: str, message_id: str) -> None:
        pass

    def create_stream(self, stream: str, properties: dict | None = None) -> dict:
        path = self._stream_path(stream)
        if not os.path.exists(path):
            open(path, "w").close()
        return {"status": "success"}

    def delete_stream(self, stream: str) -> None:
        path = self._stream_path(stream)
        if os.path.exists(path):
            os.remove(path)
        self._cursors.pop(stream, None)
