from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class NodeStatus(str, Enum):
    INITED = "INITED"
    REFINING = "REFINING"
    REFINED = "REFINED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    PLANNED = "PLANNED"
    FAILED = "FAILED"


class NodeType(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    OPERATOR = "OPERATOR"


@dataclass
class PlanNode:
    id: str
    type: NodeType
    label: str | None = None
    value: Any = None
    status: NodeStatus = NodeStatus.INITED
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanEdge:
    source: str
    target: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    id: str | None = None
    label: str | None = None
    nodes: dict[str, PlanNode] = field(default_factory=dict)
    edges: list[PlanEdge] = field(default_factory=list)
    input_node_id: str | None = None
    output_node_id: str | None = None
    provenance: str | None = None

    def add_node(self, node: PlanNode) -> PlanNode:
        self.nodes[node.id] = node
        return node

    def add_edge(self, source: str, target: str, **properties: Any) -> PlanEdge:
        edge = PlanEdge(source=source, target=target, properties=properties)
        self.edges.append(edge)
        return edge

    def get_node(self, node_id: str) -> PlanNode | None:
        return self.nodes.get(node_id)

    def set_input(self, node_id: str) -> None:
        self.input_node_id = node_id

    def set_output(self, node_id: str) -> None:
        self.output_node_id = node_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "nodes": {
                node_id: {
                    "id": node.id,
                    "type": node.type.value,
                    "label": node.label,
                    "value": node.value,
                    "status": node.status.value,
                    "properties": node.properties,
                    "metadata": node.metadata,
                }
                for node_id, node in self.nodes.items()
            },
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "properties": edge.properties,
                }
                for edge in self.edges
            ],
            "input_node_id": self.input_node_id,
            "output_node_id": self.output_node_id,
            "provenance": self.provenance,
        }

        