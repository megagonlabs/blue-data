from __future__ import annotations

from source.network.network_source import NetworkSource


class BayesianNetworkSource(NetworkSource):
    """Bayesian network source — probabilistic graphical model backend."""

    def fetch_nodes(self, network: str) -> list[str]:
        raise NotImplementedError

    def fetch_edges(self, network: str) -> list[dict]:
        raise NotImplementedError

    def infer(self, network: str, evidence: dict) -> dict:
        raise NotImplementedError

    def create_network(self, network: str, properties: dict | None = None) -> dict:
        raise NotImplementedError
