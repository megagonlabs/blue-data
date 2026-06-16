from __future__ import annotations

from blue_data.source.source import DataSource


class GraphSource(DataSource):
    """Base class for graph data sources."""

    # ---------- node operations ----------

    def add_node(self, database: str, label: str, properties: dict | None = None, node_id: str | None = None) -> str:
        raise NotImplementedError

    def get_node(self, database: str, node_id: str) -> dict | None:
        raise NotImplementedError

    def delete_node(self, database: str, node_id: str) -> None:
        raise NotImplementedError

    # ---------- edge operations ----------

    def add_edge(self, database: str, source_id: str, edge_type: str, target_id: str, properties: dict | None = None) -> str:
        raise NotImplementedError

    def delete_edge(self, database: str, source_id: str, edge_type: str, target_id: str) -> None:
        raise NotImplementedError

    # ---------- traversal ----------

    def get_neighbors(self, database: str, node_id: str, edge_type: str | None = None, direction: str = "both") -> list[dict]:
        raise NotImplementedError
