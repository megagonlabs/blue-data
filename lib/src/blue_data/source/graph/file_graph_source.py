from __future__ import annotations

import json
import logging
import os

from blue_data.source.graph.memory_graph_source import MemoryGraphSource


class FileGraphSource(MemoryGraphSource):
    """File-backed graph storage — persists nodes and edges as a JSON file per database.

    Reuses MemoryGraphSource's in-memory logic: each call loads the database's
    current state from disk into self._nodes/self._edges, delegates to the
    in-memory implementation, and writes the result back if the call mutates data.
    """

    def __init__(self, name: str, directory: str = ".", properties: dict | None = None):
        super().__init__(name, properties=properties or {})
        self.logger = logging.getLogger(self.__class__.__name__)
        self._directory = os.path.abspath(directory)
        os.makedirs(self._directory, exist_ok=True)

    # ---------- persistence helpers ----------

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

    # ---------- node operations ----------

    def add_node(self, database, label, properties=None, node_id=None) -> str:
        self._load(database)
        result = super().add_node(database, label, properties=properties, node_id=node_id)
        self._save(database)
        return result

    def get_node(self, database, node_id) -> dict | None:
        self._load(database)
        return super().get_node(database, node_id)

    def delete_node(self, database, node_id) -> None:
        self._load(database)
        super().delete_node(database, node_id)
        self._save(database)

    def update_node(self, database, node_id, properties) -> None:
        self._load(database)
        super().update_node(database, node_id, properties)
        self._save(database)

    def match_nodes(self, database, label=None, properties=None) -> list[dict]:
        self._load(database)
        return super().match_nodes(database, label=label, properties=properties)

    # ---------- edge operations ----------

    def add_edge(self, database, source_id, edge_type, target_id, properties=None) -> str:
        self._load(database)
        result = super().add_edge(database, source_id, edge_type, target_id, properties=properties)
        self._save(database)
        return result

    def delete_edge(self, database, source_id, edge_type, target_id) -> None:
        self._load(database)
        super().delete_edge(database, source_id, edge_type, target_id)
        self._save(database)

    def update_edge(self, database, source_id, edge_type, target_id, properties) -> None:
        self._load(database)
        super().update_edge(database, source_id, edge_type, target_id, properties)
        self._save(database)

    def match_edges(self, database, edge_type=None, source_id=None, target_id=None, properties=None) -> list[dict]:
        self._load(database)
        return super().match_edges(
            database, edge_type=edge_type, source_id=source_id, target_id=target_id, properties=properties
        )

    # ---------- traversal ----------

    def get_neighbors(self, database, node_id, edge_type=None, direction="both") -> list[dict]:
        self._load(database)
        return super().get_neighbors(database, node_id, edge_type=edge_type, direction=direction)

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

    def fetch_database_collection_entities(self, database, collection) -> dict:
        self._load(database)
        return super().fetch_database_collection_entities(database, collection)

    def fetch_database_collection_relations(self, database, collection) -> dict:
        self._load(database)
        return super().fetch_database_collection_relations(database, collection)

    def fetch_database_metadata(self, database) -> dict:
        self._load(database)
        return super().fetch_database_metadata(database)

    def fetch_database_schema(self, database) -> dict:
        self._load(database)
        return super().fetch_database_schema(database)

    def fetch_source_stats(self) -> dict:
        for db in self.fetch_databases():
            self._load(db)
        return super().fetch_source_stats()

    def fetch_collection_stats(self, database, collection, entities=None, relations=None, sample_limit=None) -> dict:
        self._load(database)
        return super().fetch_collection_stats(
            database, collection, entities=entities, relations=relations, sample_limit=sample_limit
        )

    def fetch_entity_stats(self, database, collection, entity) -> dict:
        self._load(database)
        return super().fetch_entity_stats(database, collection, entity)

    def fetch_property_stats(self, database, collection, entity, property_name, sample_limit=None) -> dict:
        self._load(database)
        return super().fetch_property_stats(database, collection, entity, property_name, sample_limit=sample_limit)
