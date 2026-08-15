from __future__ import annotations

from abc import ABC, abstractmethod

from blue_data.source.source import DataSource


class GraphTransaction:
    """In-progress set of changes against one database, isolated until committed.

    Holds its own working copy of nodes/edges (layered on top of whatever was
    committed when the transaction began) plus a log of the mutating operations
    applied so far. to_dict()/from_dict() round-trip a transaction verbatim, so
    a backend can persist one by dumping to_dict() and reconstruct it by
    reading the same JSON back into from_dict() — there is no separate format.
    """

    def __init__(
        self,
        transaction_id: str,
        database: str,
        nodes: dict | None = None,
        edges: dict | None = None,
        operations: list[dict] | None = None,
        status: str = "active",
    ):
        self.transaction_id = transaction_id
        self.database = database
        self.nodes = nodes if nodes is not None else {}
        self.edges = edges if edges is not None else {}
        self.operations = operations if operations is not None else []
        self.status = status

    def record(self, op: str, **kwargs) -> None:
        self.operations.append({"op": op, **kwargs})

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "database": self.database,
            "nodes": self.nodes,
            "edges": self.edges,
            "operations": self.operations,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphTransaction":
        return cls(
            data["transaction_id"],
            data["database"],
            nodes=data.get("nodes", {}),
            edges=data.get("edges", {}),
            operations=data.get("operations", []),
            status=data.get("status", "active"),
        )


class GraphSource(DataSource, ABC):
    """Base class for graph data sources."""


    # ---------- node operations ----------

    @abstractmethod
    def add_node(self, database: str, label: str, properties: dict | None = None, node_id: str | None = None, transaction_id: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_node(self, database: str, node_id: str, transaction_id: str | None = None) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def delete_node(self, database: str, node_id: str, transaction_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_node(self, database: str, node_id: str, properties: dict, transaction_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def match_nodes(self, database: str, label: str | None = None, properties: dict | None = None, transaction_id: str | None = None) -> list[dict]:
        raise NotImplementedError

    # ---------- edge operations ----------

    @abstractmethod
    def add_edge(self, database: str, source_id: str, edge_type: str, target_id: str, properties: dict | None = None, transaction_id: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete_edge(self, database: str, source_id: str, edge_type: str, target_id: str, transaction_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_edge(self, database: str, source_id: str, edge_type: str, target_id: str, properties: dict, transaction_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def match_edges(self, database: str, edge_type: str | None = None, source_id: str | None = None, target_id: str | None = None, properties: dict | None = None, transaction_id: str | None = None) -> list[dict]:
        raise NotImplementedError

    # ---------- traversal ----------

    @abstractmethod
    def get_neighbors(self, database: str, node_id: str, edge_type: str | None = None, direction: str = "both", transaction_id: str | None = None) -> list[dict]:
        raise NotImplementedError

    # ---------- query ----------

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        """Execute a compound graph operation.

        query must be a dict with:
            op – one of:
                "GRAPH.ADD_NODE"                label, properties (opt), node_id (opt)
                "GRAPH.GET_NODE"                node_id
                "GRAPH.DELETE_NODE"             node_id
                "GRAPH.UPDATE_NODE"             node_id, properties
                "GRAPH.MATCH_NODE"              label (opt), properties (opt)
                "GRAPH.ADD_EDGE"                source_id, edge_type, target_id, properties (opt)
                "GRAPH.DELETE_EDGE"             source_id, edge_type, target_id
                "GRAPH.UPDATE_EDGE"             source_id, edge_type, target_id, properties
                "GRAPH.MATCH_EDGE"              source_id (opt), edge_type (opt), target_id (opt), properties (opt)
                "GRAPH.GET_NEIGHBORS"           node_id, edge_type (opt), direction (opt, default "both")

            All node/edge ops also accept an optional "transaction_id" to read/write
            that transaction's working state instead of the committed graph. Transaction
            lifecycle (begin/commit/rollback/list/get_operations) is not part of this
            dispatch — call those methods directly on the GraphSource instance.
        """
        if not isinstance(query, dict):
            raise ValueError(
                "GraphSource.execute_query expects query as a dict with 'op' and operation-specific fields"
            )

        op = (query.get("op") or "").upper()
        transaction_id = query.get("transaction_id")

        if op == "GRAPH.ADD_NODE":
            return self.add_node(
                database,
                label=query["label"],
                properties=query.get("properties"),
                node_id=query.get("node_id"),
                transaction_id=transaction_id,
            )

        if op == "GRAPH.GET_NODE":
            return self.get_node(database, node_id=query["node_id"], transaction_id=transaction_id)

        if op == "GRAPH.DELETE_NODE":
            self.delete_node(database, node_id=query["node_id"], transaction_id=transaction_id)
            return None

        if op == "GRAPH.UPDATE_NODE":
            self.update_node(
                database, node_id=query["node_id"], properties=query["properties"], transaction_id=transaction_id
            )
            return None

        if op == "GRAPH.MATCH_NODE":
            return self.match_nodes(
                database,
                label=query.get("label"),
                properties=query.get("properties"),
                transaction_id=transaction_id,
            )

        if op == "GRAPH.ADD_EDGE":
            return self.add_edge(
                database,
                source_id=query["source_id"],
                edge_type=query["edge_type"],
                target_id=query["target_id"],
                properties=query.get("properties"),
                transaction_id=transaction_id,
            )

        if op == "GRAPH.DELETE_EDGE":
            self.delete_edge(
                database,
                source_id=query["source_id"],
                edge_type=query["edge_type"],
                target_id=query["target_id"],
                transaction_id=transaction_id,
            )
            return None

        if op == "GRAPH.UPDATE_EDGE":
            self.update_edge(
                database,
                source_id=query["source_id"],
                edge_type=query["edge_type"],
                target_id=query["target_id"],
                properties=query["properties"],
                transaction_id=transaction_id,
            )
            return None

        if op == "GRAPH.MATCH_EDGE":
            return self.match_edges(
                database,
                edge_type=query.get("edge_type"),
                source_id=query.get("source_id"),
                target_id=query.get("target_id"),
                properties=query.get("properties"),
                transaction_id=transaction_id,
            )

        if op == "GRAPH.GET_NEIGHBORS":
            return self.get_neighbors(
                database,
                node_id=query["node_id"],
                edge_type=query.get("edge_type"),
                direction=query.get("direction", "both"),
                transaction_id=transaction_id,
            )

        raise ValueError(
            f"Unsupported GraphSource operation: {op!r}. "
            "Supported: GRAPH.ADD_NODE, GRAPH.GET_NODE, GRAPH.DELETE_NODE, GRAPH.UPDATE_NODE, GRAPH.MATCH_NODE, "
            "GRAPH.ADD_EDGE, GRAPH.DELETE_EDGE, GRAPH.UPDATE_EDGE, GRAPH.MATCH_EDGE, GRAPH.GET_NEIGHBORS"
        )
