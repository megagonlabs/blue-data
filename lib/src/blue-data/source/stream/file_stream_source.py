from __future__ import annotations

from source.stream.stream_source import StreamSource


class FileStreamSource(StreamSource):
    """File-backed stream source — appends JSON lines to per-stream files."""

    def publish(self, stream: str, message: dict) -> None:
        raise NotImplementedError

    def consume(self, stream: str, count: int = 1) -> list[dict]:
        raise NotImplementedError

    def acknowledge(self, stream: str, message_id: str) -> None:
        raise NotImplementedError

    def create_stream(self, stream: str, properties: dict | None = None) -> dict:
        raise NotImplementedError

    def delete_stream(self, stream: str) -> None:
        raise NotImplementedError
