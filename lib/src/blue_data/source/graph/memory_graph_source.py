from __future__ import annotations

import copy
import uuid
from collections import defaultdict

from blue_data.source.graph.graph_source import GraphSource, GraphTransaction


class MemoryGraphSource(GraphSource):
    """In-memory graph storage backend for local/dev/test use."""

    def __init__(self, name: str, properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._nodes: dict[str, dict[str, dict]] = defaultdict(dict)
        self._edges: dict[str, dict[str, dict]] = defaultdict(dict)
        self._transactions: dict[str, GraphTransaction] = {}

    # ---------- transaction helpers ----------

    def _require_transaction(self, transaction_id: str) -> GraphTransaction:
        txn = self._transactions.get(transaction_id)
        if txn is None:
            raise KeyError(f"No active transaction with id {transaction_id!r}")
        return txn

    def _resolve(self, database: str, transaction_id: str | None):
        """Return (nodes, edges, operations_log_or_None) to operate on.

        transaction_id=None targets the committed graph directly; otherwise
        targets that transaction's isolated working copy, and mutations get
        appended to its operations log.
        """
        if transaction_id is None:
            return self._nodes[database], self._edges[database], None
        txn = self._require_transaction(transaction_id)
        if txn.database != database:
            raise ValueError(
                f"transaction {transaction_id!r} belongs to database {txn.database!r}, not {database!r}"
            )
        return txn.nodes, txn.edges, txn.operations

    # ---------- node operations ----------

    def add_node(self, database, label, properties=None, node_id=None, transaction_id=None) -> str:
        node_id = node_id or str(uuid.uuid4())
        nodes, _, log = self._resolve(database, transaction_id)
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": properties or {},
        }
        if log is not None:
            log.append({"op": "add_node", "label": label, "properties": properties, "node_id": node_id})
        return node_id

    def get_node(self, database, node_id, transaction_id=None) -> dict | None:
        nodes, _, _ = self._resolve(database, transaction_id)
        return nodes.get(node_id)

    def delete_node(self, database, node_id, transaction_id=None) -> None:
        nodes, edges, log = self._resolve(database, transaction_id)
        nodes.pop(node_id, None)
        stale = [eid for eid, e in edges.items() if e["source_id"] == node_id or e["target_id"] == node_id]
        for eid in stale:
            del edges[eid]
        if log is not None:
            log.append({"op": "delete_node", "node_id": node_id})

    def update_node(self, database, node_id, properties, transaction_id=None) -> None:
        nodes, _, log = self._resolve(database, transaction_id)
        node = nodes.get(node_id)
        if node is not None:
            node["properties"].update(properties)
            if log is not None:
                log.append({"op": "update_node", "node_id": node_id, "properties": properties})

    def match_nodes(self, database, label=None, properties=None, transaction_id=None) -> list[dict]:
        nodes, _, _ = self._resolve(database, transaction_id)
        results = []
        for node in nodes.values():
            if label is not None and node["label"] != label:
                continue
            if properties and not all(node["properties"].get(k) == v for k, v in properties.items()):
                continue
            results.append(node)
        return results

    # ---------- edge operations ----------

    def add_edge(self, database, source_id, edge_type, target_id, properties=None, transaction_id=None) -> str:
        edge_id = str(uuid.uuid4())
        _, edges, log = self._resolve(database, transaction_id)
        edges[edge_id] = {
            "id": edge_id,
            "source_id": source_id,
            "edge_type": edge_type,
            "target_id": target_id,
            "properties": properties or {},
        }
        if log is not None:
            log.append({
                "op": "add_edge", "source_id": source_id, "edge_type": edge_type,
                "target_id": target_id, "properties": properties, "edge_id": edge_id,
            })
        return edge_id

    def delete_edge(self, database, source_id, edge_type, target_id, transaction_id=None) -> None:
        _, edges, log = self._resolve(database, transaction_id)
        stale = [
            eid for eid, e in edges.items()
            if e["source_id"] == source_id and e["edge_type"] == edge_type and e["target_id"] == target_id
        ]
        for eid in stale:
            del edges[eid]
        if log is not None:
            log.append({
                "op": "delete_edge", "source_id": source_id, "edge_type": edge_type, "target_id": target_id,
            })

    def update_edge(self, database, source_id, edge_type, target_id, properties, transaction_id=None) -> None:
        _, edges, log = self._resolve(database, transaction_id)
        changed = False
        for edge in edges.values():
            if (
                edge["source_id"] == source_id
                and edge["edge_type"] == edge_type
                and edge["target_id"] == target_id
            ):
                edge["properties"].update(properties)
                changed = True
        if changed and log is not None:
            log.append({
                "op": "update_edge", "source_id": source_id, "edge_type": edge_type,
                "target_id": target_id, "properties": properties,
            })

    def match_edges(self, database, edge_type=None, source_id=None, target_id=None, properties=None, transaction_id=None) -> list[dict]:
        _, edges, _ = self._resolve(database, transaction_id)
        results = []
        for edge in edges.values():
            if edge_type is not None and edge["edge_type"] != edge_type:
                continue
            if source_id is not None and edge["source_id"] != source_id:
                continue
            if target_id is not None and edge["target_id"] != target_id:
                continue
            if properties and not all(edge["properties"].get(k) == v for k, v in properties.items()):
                continue
            results.append(edge)
        return results

    # ---------- traversal ----------

    def get_neighbors(self, database, node_id, edge_type=None, direction="both", transaction_id=None) -> list[dict]:
        nodes, edges, _ = self._resolve(database, transaction_id)
        results = []
        for edge in edges.values():
            if edge_type and edge["edge_type"] != edge_type:
                continue
            if direction in ("out", "both") and edge["source_id"] == node_id:
                neighbor = nodes.get(edge["target_id"])
                if neighbor:
                    results.append({"node": neighbor, "edge": edge, "direction": "out"})
            if direction in ("in", "both") and edge["target_id"] == node_id:
                neighbor = nodes.get(edge["source_id"])
                if neighbor:
                    results.append({"node": neighbor, "edge": edge, "direction": "in"})
        return results

    # ---------- transactions ----------

    def begin_transaction(self, database: str) -> str:
        transaction_id = str(uuid.uuid4())
        self._transactions[transaction_id] = GraphTransaction(
            transaction_id,
            database,
            nodes=copy.deepcopy(self._nodes[database]),
            edges=copy.deepcopy(self._edges[database]),
        )
        return transaction_id

    def commit_transaction(self, transaction_id: str) -> None:
        txn = self._require_transaction(transaction_id)
        self._nodes[txn.database] = txn.nodes
        self._edges[txn.database] = txn.edges
        del self._transactions[transaction_id]

    def rollback_transaction(self, transaction_id: str) -> None:
        self._require_transaction(transaction_id)
        del self._transactions[transaction_id]

    def get_transaction_operations(self, transaction_id: str) -> list[dict]:
        return list(self._require_transaction(transaction_id).operations)

    def list_transactions(self, database: str | None = None) -> list[str]:
        return [
            tid for tid, txn in self._transactions.items()
            if database is None or txn.database == database
        ]

    # ---------- DataSource interface ----------

    def create_database(self, database, properties=None, overwrite=False) -> dict:
        if database in self._nodes and not overwrite:
            return {"status": "skipped"}
        self._nodes[database] = {}
        self._edges[database] = {}
        return {"status": "success"}

    def fetch_databases(self) -> list[str]:
        return list(set(list(self._nodes.keys()) + list(self._edges.keys())))

    def fetch_database_collections(self, database) -> list[str]:
        return [database]

    def fetch_database_collection_entities(self, database, collection, transaction_id=None) -> dict:
        nodes, _, _ = self._resolve(database, transaction_id)
        label_props: dict[str, dict] = {}
        for node in nodes.values():
            label = node["label"]
            if label not in label_props:
                label_props[label] = {}
            for k, v in node["properties"].items():
                label_props[label].setdefault(k, type(v).__name__)

        return {
            label: {
                "properties": {},
                "contents": {
                    "attributes": {
                        prop: {"name": prop, "info": {"type": dtype, "values": []}}
                        for prop, dtype in props.items()
                    }
                },
            }
            for label, props in label_props.items()
        }

    def fetch_database_collection_relations(self, database, collection, transaction_id=None) -> dict:
        nodes, edges, _ = self._resolve(database, transaction_id)
        relations: dict[str, dict] = {}
        for edge in edges.values():
            edge_type = edge["edge_type"]
            if edge_type not in relations:
                source_label = (nodes.get(edge["source_id"]) or {}).get("label", "")
                target_label = (nodes.get(edge["target_id"]) or {}).get("label", "")
                relations[edge_type] = {
                    "properties": {"source_entity": source_label, "target_entity": target_label},
                    "contents": {"attributes": {}},
                }
        return relations

    def fetch_metadata(self) -> dict:
        return {"name": self.name, "type": "graph"}

    def fetch_database_metadata(self, database, transaction_id=None) -> dict:
        nodes, edges, _ = self._resolve(database, transaction_id)
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def fetch_database_schema(self, database, transaction_id=None) -> dict:
        nodes, edges, _ = self._resolve(database, transaction_id)
        labels = {n["label"] for n in nodes.values()}
        edge_types = {e["edge_type"] for e in edges.values()}
        return {"node_labels": sorted(labels), "edge_types": sorted(edge_types)}

    def fetch_database_collection_metadata(self, database, collection, transaction_id=None) -> dict:
        return self.fetch_database_metadata(database, transaction_id=transaction_id)

    def create_database_collection(self, database, collection, properties=None) -> dict:
        return {}

    def fetch_source_stats(self) -> dict:
        return {
            "total_nodes": sum(len(n) for n in self._nodes.values()),
            "total_edges": sum(len(e) for e in self._edges.values()),
        }

    def fetch_database_stats(self, database, transaction_id=None) -> dict:
        return self.fetch_database_metadata(database, transaction_id=transaction_id)

    def fetch_collection_stats(self, database, collection, entities=None, relations=None, sample_limit=None, transaction_id=None) -> dict:
        nodes, edges, _ = self._resolve(database, transaction_id)
        return {
            "num_entities": len(entities or []),
            "num_relations": len(relations or []),
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def fetch_entity_stats(self, database, collection, entity, transaction_id=None) -> dict:
        nodes, _, _ = self._resolve(database, transaction_id)
        count = sum(1 for n in nodes.values() if n["label"] == entity)
        return {"row_count": count, "node_count": count}

    def fetch_property_stats(self, database, collection, entity, property_name, sample_limit=None, transaction_id=None) -> dict:
        from collections import Counter
        nodes, _, _ = self._resolve(database, transaction_id)
        values = [
            node["properties"][property_name]
            for node in nodes.values()
            if node["label"] == entity and property_name in node["properties"]
        ]
        if sample_limit:
            values = values[:sample_limit]
        counts = Counter(str(v) for v in values)
        return {
            "count": len(values),
            "unique_count": len(counts),
            "most_common": [{"value": v, "count": c} for v, c in counts.most_common(10)],
        }
