from __future__ import annotations

import json
import logging
import os

import numpy as np

from source.vector.vector_source import VectorSource


class FileVectorSource(VectorSource):
    """File-backed vector storage — persists docs as JSON files per collection."""

    def __init__(self, name: str, directory: str = ".", properties: dict | None = None):
        super().__init__(name, properties=properties or {})
        self.logger = logging.getLogger(self.__class__.__name__)
        self._directory = os.path.abspath(directory)
        os.makedirs(self._directory, exist_ok=True)
        self._indices: dict[str, dict] = self._load_indices()

    # ---------- persistence helpers ----------

    def _indices_path(self) -> str:
        return os.path.join(self._directory, "_indices.json")

    def _collection_path(self, collection: str) -> str:
        return os.path.join(self._directory, collection + ".json")

    def _load_indices(self) -> dict:
        path = self._indices_path()
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {}

    def _save_indices(self) -> None:
        with open(self._indices_path(), "w") as f:
            json.dump(self._indices, f)

    def _load_collection(self, collection: str) -> dict:
        path = self._collection_path(collection)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {}

    def _save_collection(self, collection: str, docs: dict) -> None:
        with open(self._collection_path(collection), "w") as f:
            json.dump(docs, f)

    # ---------- cosine distance ----------

    def _cosine_distance(self, a, b) -> float:
        va = np.asarray(a, dtype=np.float32)
        vb = np.asarray(b, dtype=np.float32)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))

    # ---------- execute_query ----------

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        if not isinstance(query, dict):
            raise Exception("FileVectorSource expects query as a dict")

        op = query.get("op", "").upper()

        if op == "VECTOR.CREATE_INDEX":
            index_name = query.get("index")
            coll = query.get("collection")
            dim = query.get("dim")
            if not index_name or not coll or dim is None:
                raise Exception("VECTOR.CREATE_INDEX requires index, collection, dim")
            self._indices[index_name] = {
                "collection": coll,
                "dim": int(dim),
                "metric": query.get("distance_metric", "COSINE"),
            }
            self._save_indices()
            if not os.path.exists(self._collection_path(coll)):
                self._save_collection(coll, {})
            return "OK"

        if op == "VECTOR.UPSERT":
            coll = query.get("collection")
            doc_id = query.get("id")
            doc = query.get("doc")
            embedding_field = query.get("embedding_field", "embedding")
            if not coll or not doc_id:
                raise Exception("VECTOR.UPSERT requires collection and id")
            if doc is None or embedding_field not in doc:
                raise Exception(f"VECTOR.UPSERT requires doc with '{embedding_field}' field")
            docs = self._load_collection(coll)
            docs[doc_id] = doc
            self._save_collection(coll, docs)
            return "OK"

        if op == "VECTOR.DELETE":
            coll = query.get("collection")
            doc_id = query.get("id")
            if not coll or not doc_id:
                raise Exception("VECTOR.DELETE requires collection and id")
            docs = self._load_collection(coll)
            docs.pop(doc_id, None)
            self._save_collection(coll, docs)
            return 1

        if op == "VECTOR.KNN":
            index_name = query.get("index")
            if not index_name:
                raise Exception("VECTOR.KNN requires index")
            if index_name not in self._indices:
                return []

            query_vector = (
                query.get("vector")
                or query.get("embedding")
                or query.get("query_vector")
                or query.get("query_embedding")
            )
            if query_vector is None:
                raise Exception("VECTOR.KNN requires a query vector")

            k = int(query.get("k", 5))
            embedding_field = query.get("field") or query.get("vector_field", "embedding")
            score_alias = query.get("score_alias") or query.get("score_field", "score")
            return_fields: list[str] = list(query.get("return_fields") or [])

            coll = self._indices[index_name]["collection"]
            docs = self._load_collection(coll)

            scored = []
            for doc_id, doc in docs.items():
                emb = doc.get(embedding_field)
                if emb is None:
                    continue
                dist = self._cosine_distance(query_vector, emb)
                scored.append((dist, doc_id, doc))

            scored.sort(key=lambda x: x[0])

            results = []
            for dist, doc_id, doc in scored[:k]:
                row: dict = {"id": doc_id, score_alias: dist}
                if return_fields:
                    for field in return_fields:
                        if field != score_alias and field in doc:
                            row[field] = doc[field]
                else:
                    for field, val in doc.items():
                        if field != embedding_field:
                            row[field] = val
                results.append(row)

            return results

        raise Exception(f"Unsupported vector operation: {op}")
