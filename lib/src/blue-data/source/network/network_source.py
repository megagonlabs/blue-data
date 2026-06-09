from __future__ import annotations

from source.source import DataSource


class NetworkSource(DataSource):
    """Base class for probabilistic / graph network data sources."""

    def fetch_nodes(self, network: str) -> list[str]:
        raise NotImplementedError

    def fetch_edges(self, network: str) -> list[dict]:
        raise NotImplementedError

    def infer(self, network: str, evidence: dict) -> dict:
        raise NotImplementedError

    def create_network(self, network: str, properties: dict | None = None) -> dict:
        raise NotImplementedError
