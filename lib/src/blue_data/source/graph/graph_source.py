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

    # ---------- tool-based nl2q ----------

    def get_nl_tools(self, database=None, collection=None):
        base = super().get_nl_tools(database=database, collection=collection)
        # Keep list_databases, list_collections, get_schema, get_metadata.
        # Replace execute_query with graph-specific traversal tools.
        graph_tools = [t for t in base if t["name"] != "execute_query"]
        graph_tools += [
            {
                "name": "match_nodes",
                "description": "Find nodes in the graph by label and/or property values.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "label": {"type": "string", "description": "Node label to filter by"},
                        "properties": {
                            "type": "object",
                            "description": "Key/value pairs the node must match",
                        },
                    },
                    "required": ["database"],
                },
            },
            {
                "name": "get_node",
                "description": "Fetch a single node by its ID.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "node_id": {"type": "string"},
                    },
                    "required": ["database", "node_id"],
                },
            },
            {
                "name": "get_neighbors",
                "description": "Get neighbouring nodes connected to a given node, optionally filtered by edge type and direction.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "node_id": {"type": "string"},
                        "edge_type": {"type": "string", "description": "Edge/relationship type to filter by"},
                        "direction": {
                            "type": "string",
                            "enum": ["in", "out", "both"],
                            "description": "Traversal direction (default: both)",
                        },
                    },
                    "required": ["database", "node_id"],
                },
            },
            {
                "name": "match_edges",
                "description": "Find edges/relationships in the graph by type and/or endpoint node IDs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "edge_type": {"type": "string"},
                        "source_id": {"type": "string"},
                        "target_id": {"type": "string"},
                    },
                    "required": ["database"],
                },
            },
        ]
        return graph_tools

    def execute_nl_tool(self, name, tool_input, database=None, collection=None, optional_properties=None):
        db = tool_input.get("database", database)

        if name == "match_nodes":
            return self.match_nodes(
                db,
                label=tool_input.get("label"),
                properties=tool_input.get("properties"),
            )
        if name == "get_node":
            return self.get_node(db, tool_input["node_id"])
        if name == "get_neighbors":
            return self.get_neighbors(
                db,
                node_id=tool_input["node_id"],
                edge_type=tool_input.get("edge_type"),
                direction=tool_input.get("direction", "both"),
            )
        if name == "match_edges":
            return self.match_edges(
                db,
                edge_type=tool_input.get("edge_type"),
                source_id=tool_input.get("source_id"),
                target_id=tool_input.get("target_id"),
            )
        return super().execute_nl_tool(name, tool_input, database=database, collection=collection, optional_properties=optional_properties)

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
