from __future__ import annotations

from collections import defaultdict

from source.stream.stream_source import StreamSource


class MemoryStreamSource(StreamSource):
    """In-memory stream backend for local/dev/test use."""

    def __init__(self, name: str, properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._streams: dict[str, list[dict]] = defaultdict(list)
        self._cursor: dict[str, int] = {}

    def publish(self, stream: str, message: dict) -> None:
        self._streams[stream].append(message)

    def consume(self, stream: str, count: int = 1) -> list[dict]:
        cursor = self._cursor.get(stream, 0)
        messages = self._streams[stream][cursor : cursor + count]
        self._cursor[stream] = cursor + len(messages)
        return messages

    def acknowledge(self, stream: str, message_id: str) -> None:
        pass

    def create_stream(self, stream: str, properties: dict | None = None) -> dict:
        self._streams.setdefault(stream, [])
        return {"status": "success"}

    def delete_stream(self, stream: str) -> None:
        self._streams.pop(stream, None)
        self._cursor.pop(stream, None)
