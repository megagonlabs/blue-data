from __future__ import annotations

import json
import logging
import os

from blue_data.source.graph.graph_source import GraphTransaction
from blue_data.source.graph.memory_graph_source import MemoryGraphSource


class FileGraphSource(MemoryGraphSource):
    """File-backed graph storage — persists nodes and edges as a JSON file per database.

    Reuses MemoryGraphSource's in-memory logic: each call loads the database's
    current state from disk into self._nodes/self._edges, delegates to the
    in-memory implementation, and writes the result back if the call mutates data.

    Transactions are persisted the same way: a transaction is nothing more than
    GraphTransaction.to_dict() written to a sidecar file, and it's reconstructed
    by reading that file back into GraphTransaction.from_dict(). That sidecar is
    rewritten after every mutating call within the transaction, so an in-progress
    transaction's working state survives a process restart and can be inspected
    or resumed by a fresh FileGraphSource instance that never called
    begin_transaction() itself.
    """

    def __init__(self, name: str, directory: str | None = None, properties: dict | None = None):
        props = dict(properties or {})
        if directory is not None:
            props.setdefault("connection", {})["directory"] = directory
        super().__init__(name, properties=props)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._directory = os.path.abspath(self.properties["connection"]["directory"])
        os.makedirs(self._directory, exist_ok=True)

    def _initialize_connection_properties(self) -> None:
        conn = self.properties.get("connection", {})
        conn.setdefault("protocol", "graph")
        conn.setdefault("subprotocol", "file")
        conn.setdefault("directory", ".")
        self.properties["connection"] = conn

    # ---------- persistence helpers (committed database) ----------

    def _db_path(self, database: str) -> str:
        return os.path.join(self._directory, database + ".json")

    def _load(self, database: str) -> None:
        path = self._db_path(database)
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        else:
            data = {"nodes": {}, "edges": {}}
        self._nodes[database] = data["nodes"]
        self._edges[database] = data["edges"]

    def _save(self, database: str) -> None:
        with open(self._db_path(database), "w") as f:
            json.dump({"nodes": self._nodes[database], "edges": self._edges[database]}, f)

    # ---------- persistence helpers (transactions) ----------

    def _txn_path(self, database: str, transaction_id: str) -> str:
        return os.path.join(self._directory, f"{database}#{transaction_id}.txn")

    def _hydrate_transaction(self, transaction_id: str) -> None:
        """Ensure self._transactions[transaction_id] reflects disk, loading it if needed."""
        if transaction_id in self._transactions:
            return
        for fname in os.listdir(self._directory):
            if fname.endswith(f"#{transaction_id}.txn"):
                with open(os.path.join(self._directory, fname)) as f:
                    self._transactions[transaction_id] = GraphTransaction.from_dict(json.load(f))
                return
        raise KeyError(f"No active transaction with id {transaction_id!r}")

    def _persist_transaction(self, transaction_id: str) -> None:
        txn = self._transactions[transaction_id]
        with open(self._txn_path(txn.database, transaction_id), "w") as f:
            json.dump(txn.to_dict(), f)

    def _delete_transaction_file(self, database: str, transaction_id: str) -> None:
        path = self._txn_path(database, transaction_id)
        if os.path.exists(path):
            os.remove(path)

    def _begin_call(self, database: str, transaction_id: str | None) -> None:
        if transaction_id is None:
            self._load(database)
        else:
            self._hydrate_transaction(transaction_id)

    def _end_call(self, database: str, transaction_id: str | None) -> None:
        if transaction_id is None:
            self._save(database)
        else:
            self._persist_transaction(transaction_id)

    # ---------- node operations ----------

    def add_node(self, database, label, properties=None, node_id=None, transaction_id=None) -> str:
        self._begin_call(database, transaction_id)
        result = super().add_node(database, label, properties=properties, node_id=node_id, transaction_id=transaction_id)
        self._end_call(database, transaction_id)
        return result

    def get_node(self, database, node_id, transaction_id=None) -> dict | None:
        self._begin_call(database, transaction_id)
        return super().get_node(database, node_id, transaction_id=transaction_id)

    def delete_node(self, database, node_id, transaction_id=None) -> None:
        self._begin_call(database, transaction_id)
        super().delete_node(database, node_id, transaction_id=transaction_id)
        self._end_call(database, transaction_id)

    def update_node(self, database, node_id, properties, transaction_id=None) -> None:
        self._begin_call(database, transaction_id)
        super().update_node(database, node_id, properties, transaction_id=transaction_id)
        self._end_call(database, transaction_id)

    def match_nodes(self, database, label=None, properties=None, transaction_id=None) -> list[dict]:
        self._begin_call(database, transaction_id)
        return super().match_nodes(database, label=label, properties=properties, transaction_id=transaction_id)

    # ---------- edge operations ----------

    def add_edge(self, database, source_id, edge_type, target_id, properties=None, transaction_id=None) -> str:
        self._begin_call(database, transaction_id)
        result = super().add_edge(
            database, source_id, edge_type, target_id, properties=properties, transaction_id=transaction_id
        )
        self._end_call(database, transaction_id)
        return result

    def delete_edge(self, database, source_id, edge_type, target_id, transaction_id=None) -> None:
        self._begin_call(database, transaction_id)
        super().delete_edge(database, source_id, edge_type, target_id, transaction_id=transaction_id)
        self._end_call(database, transaction_id)

    def update_edge(self, database, source_id, edge_type, target_id, properties, transaction_id=None) -> None:
        self._begin_call(database, transaction_id)
        super().update_edge(database, source_id, edge_type, target_id, properties, transaction_id=transaction_id)
        self._end_call(database, transaction_id)

    def match_edges(self, database, edge_type=None, source_id=None, target_id=None, properties=None, transaction_id=None) -> list[dict]:
        self._begin_call(database, transaction_id)
        return super().match_edges(
            database, edge_type=edge_type, source_id=source_id, target_id=target_id,
            properties=properties, transaction_id=transaction_id,
        )

    # ---------- traversal ----------

    def get_neighbors(self, database, node_id, edge_type=None, direction="both", transaction_id=None) -> list[dict]:
        self._begin_call(database, transaction_id)
        return super().get_neighbors(
            database, node_id, edge_type=edge_type, direction=direction, transaction_id=transaction_id
        )

    # ---------- transactions ----------

    def begin_transaction(self, database: str) -> str:
        self._load(database)
        transaction_id = super().begin_transaction(database)
        self._persist_transaction(transaction_id)
        return transaction_id

    def commit_transaction(self, transaction_id: str) -> None:
        self._hydrate_transaction(transaction_id)
        database = self._transactions[transaction_id].database
        super().commit_transaction(transaction_id)
        self._save(database)
        self._delete_transaction_file(database, transaction_id)

    def rollback_transaction(self, transaction_id: str) -> None:
        self._hydrate_transaction(transaction_id)
        database = self._transactions[transaction_id].database
        super().rollback_transaction(transaction_id)
        self._delete_transaction_file(database, transaction_id)

    def get_transaction_operations(self, transaction_id: str) -> list[dict]:
        self._hydrate_transaction(transaction_id)
        return super().get_transaction_operations(transaction_id)

    def list_transactions(self, database: str | None = None) -> list[str]:
        """Lightweight listing: parses sidecar filenames only, never loads/instantiates them."""
        results = []
        for fname in os.listdir(self._directory):
            if not fname.endswith(".txn"):
                continue
            db, sep, transaction_id = fname[: -len(".txn")].rpartition("#")
            if not sep:
                continue
            if database is not None and db != database:
                continue
            results.append(transaction_id)
        return results

    # ---------- DataSource interface ----------

    def create_database(self, database, properties=None, overwrite=False) -> dict:
        path = self._db_path(database)
        if os.path.exists(path) and not overwrite:
            return {"status": "skipped"}
        self._nodes[database] = {}
        self._edges[database] = {}
        self._save(database)
        return {"status": "success"}

    def fetch_databases(self) -> list[str]:
        return [f[:-5] for f in os.listdir(self._directory) if f.endswith(".json")]

    def fetch_database_collection_entities(self, database, collection, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_database_collection_entities(database, collection, transaction_id=transaction_id)

    def fetch_database_collection_relations(self, database, collection, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_database_collection_relations(database, collection, transaction_id=transaction_id)

    def fetch_database_metadata(self, database, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_database_metadata(database, transaction_id=transaction_id)

    def fetch_database_schema(self, database, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_database_schema(database, transaction_id=transaction_id)

    def fetch_source_stats(self) -> dict:
        for db in self.fetch_databases():
            self._load(db)
        return super().fetch_source_stats()

    def fetch_collection_stats(self, database, collection, entities=None, relations=None, sample_limit=None, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_collection_stats(
            database, collection, entities=entities, relations=relations,
            sample_limit=sample_limit, transaction_id=transaction_id,
        )

    def fetch_entity_stats(self, database, collection, entity, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_entity_stats(database, collection, entity, transaction_id=transaction_id)

    def fetch_property_stats(self, database, collection, entity, property_name, sample_limit=None, transaction_id=None) -> dict:
        self._begin_call(database, transaction_id)
        return super().fetch_property_stats(
            database, collection, entity, property_name, sample_limit=sample_limit, transaction_id=transaction_id
        )
