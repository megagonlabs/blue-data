from __future__ import annotations

from source.source import DataSource


class StreamSource(DataSource):
    """Base class for stream data sources."""

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
