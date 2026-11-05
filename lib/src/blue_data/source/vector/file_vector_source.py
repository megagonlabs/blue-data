from __future__ import annotations

import json
import os

import numpy as np

from blue_data.core.utils.file_lock import file_lock, write_json_atomic
from blue_data.source.vector.vector_source import VectorSource


class FileVectorSource(VectorSource):
    """File-backed vector storage — persists docs as JSON files per collection."""

    def __init__(self, name: str, directory: str | None = None, embedding_fn=None, properties: dict | None = None):
        props = dict(properties or {})
        if directory is not None:
            props.setdefault("connection", {})["directory"] = directory
        super().__init__(name, embedding_fn=embedding_fn, properties=props)
        # A required setting, not defaulted to ".": defaulting to the cwd scattered
        # index/vector files across whatever directory the process ran from, so one
        # run's data couldn't be found by the next and stray files landed in checkouts. #227
        directory = self.properties["connection"].get("directory")
        if not directory:
            raise ValueError(
                "FileVectorSource requires connection.directory (or the directory= "
                "argument); it does not default to the current working directory."
            )
        self._directory = os.path.abspath(directory)
        os.makedirs(self._directory, exist_ok=True)
        self._indices: dict[str, dict] = self._load_indices()

    def _initialize_connection_properties(self) -> None:
        conn = self.properties.get("connection", {})
        conn.setdefault("protocol", "vector/file")
        self.properties["connection"] = conn

    # ---------- persistence helpers ----------

    def _indices_path(self) -> str:
        return os.path.join(self._directory, "_indices.json")

    def _collection_path(self, collection: str) -> str:
        return os.path.join(self._directory, collection + ".json")

    @staticmethod
    def _read_json(path: str) -> dict:
        """Read a JSON file, returning {} when absent. Names the file on a parse
        error so a corrupt store is diagnosable, not an anonymous JSONDecodeError
        (#272). Atomic writes (below) make a torn read impossible for live files."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError) as exc:
            raise ValueError(f"FileVectorSource: cannot read {path!r}: {exc}") from exc

    def _load_indices(self) -> dict:
        return self._read_json(self._indices_path())

    def _save_indices(self) -> None:
        # Atomic replace + 0600 (like FileJSONSource) so an interrupted write never
        # leaves invalid JSON and the embeddings/names aren't world/group-readable. #272
        write_json_atomic(self._indices_path(), self._indices, mode=0o600)

    def _load_collection(self, collection: str) -> dict:
        return self._read_json(self._collection_path(collection))

    def _save_collection(self, collection: str, docs: dict) -> None:
        write_json_atomic(self._collection_path(collection), docs, mode=0o600)

    # ---------- cosine distance ----------

    def _cosine_distance(self, a, b) -> float:
        va = np.asarray(a, dtype=np.float32)
        vb = np.asarray(b, dtype=np.float32)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))

    # ---------- primitive operations ----------

    def create_index(self, index_name: str, collection: str, dim: int, distance_metric: str = "COSINE", extra_fields: list | None = None) -> str:
        # Reload under the lock before merging so a concurrent create_index in
        # another process isn't clobbered by this process's stale in-memory copy. #272
        with file_lock(self._indices_path()):
            self._indices = self._load_indices()
            self._indices[index_name] = {
                "collection": collection,
                "dim": int(dim),
                "metric": distance_metric,
            }
            self._save_indices()
        with file_lock(self._collection_path(collection)):
            if not os.path.exists(self._collection_path(collection)):
                self._save_collection(collection, {})
        return "OK"

    def upsert(self, collection: str, doc_id: str, doc: dict, embedding_field: str = "embedding") -> str:
        if embedding_field not in doc:
            raise Exception(f"VECTOR.UPSERT requires doc with '{embedding_field}' field")
        # Hold the per-collection lock across the whole read-modify-write: each
        # writer rewrites the entire collection, so without it concurrent upserts
        # lose documents (#272).
        with file_lock(self._collection_path(collection)):
            docs = self._load_collection(collection)
            docs[doc_id] = doc
            self._save_collection(collection, docs)
        return "OK"

    def delete(self, collection: str, doc_id: str) -> int:
        # Return the number of documents actually removed (0 or 1), matching the
        # VectorSource contract and RedisVectorSource — not 1 unconditionally.
        with file_lock(self._collection_path(collection)):
            docs = self._load_collection(collection)
            if doc_id not in docs:
                return 0
            del docs[doc_id]
            self._save_collection(collection, docs)
        return 1

    def list_ids(self, collection: str, prefix: str | None = None) -> list[str]:
        ids = list(self._load_collection(collection).keys())
        if prefix:
            ids = [doc_id for doc_id in ids if doc_id.startswith(prefix)]
        return ids

    def delete_by_prefix(self, collection: str, prefix: str) -> int:
        # One load/save for the whole prefix, not one file rewrite per id.
        with file_lock(self._collection_path(collection)):
            docs = self._load_collection(collection)
            to_remove = [doc_id for doc_id in docs if doc_id.startswith(prefix)]
            for doc_id in to_remove:
                del docs[doc_id]
            if to_remove:
                self._save_collection(collection, docs)
        return len(to_remove)

    def knn(
        self,
        index_name: str,
        query_vector: list,
        k: int = 5,
        embedding_field: str = "embedding",
        score_alias: str = "score",
        return_fields: list[str] | None = None,
        filter_expr: str = "*",
    ) -> list[dict]:
        if index_name not in self._indices:
            return []

        return_fields = return_fields or []
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

    # ---------- DataSource interface ----------

    def fetch_databases(self) -> list[str]:
        return ["default"]

    def fetch_database_collections(self, database: str) -> list[str]:
        return [
            f[:-5] for f in os.listdir(self._directory)
            if f.endswith(".json") and not f.startswith("_")
        ]

    def fetch_database_collection_metadata(self, database: str, collection: str) -> dict:
        return {"doc_count": len(self._load_collection(collection))}

    def fetch_source_stats(self) -> dict:
        collections = self.fetch_database_collections("default")
        total = sum(len(self._load_collection(c)) for c in collections)
        return {"total_collections": len(collections), "total_docs": total}

    def fetch_collection_stats(self, database: str, collection: str, entities=None, relations=None, sample_limit=None) -> dict:
        return {"doc_count": len(self._load_collection(collection))}
