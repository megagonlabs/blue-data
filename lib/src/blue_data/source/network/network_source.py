from __future__ import annotations

from blue_data.source.source import DataSource


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

    # ---------- query ----------

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        """Execute a compound network operation.

        query must be a dict with:
            op – one of:
                "NETWORK.FETCH_NODES" network
                "NETWORK.FETCH_EDGES" network
                "NETWORK.INFER"       network, evidence
                "NETWORK.CREATE"      network, properties (opt)
        """
        if not isinstance(query, dict):
            raise ValueError(
                "NetworkSource.execute_query expects query as a dict with 'op' and operation-specific fields"
            )

        op = (query.get("op") or "").upper()

        if op == "NETWORK.FETCH_NODES":
            return self.fetch_nodes(network=query["network"])

        if op == "NETWORK.FETCH_EDGES":
            return self.fetch_edges(network=query["network"])

        if op == "NETWORK.INFER":
            return self.infer(network=query["network"], evidence=query["evidence"])

        if op == "NETWORK.CREATE":
            return self.create_network(network=query["network"], properties=query.get("properties"))

        raise ValueError(
            f"Unsupported NetworkSource operation: {op!r}. "
            "Supported: NETWORK.FETCH_NODES, NETWORK.FETCH_EDGES, NETWORK.INFER, NETWORK.CREATE"
        )
