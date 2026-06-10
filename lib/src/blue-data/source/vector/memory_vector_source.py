from __future__ import annotations

import logging
import re

import numpy as np

from source.vector.vector_source import VectorSource


class MemoryVectorSource(VectorSource):
    """In-memory vector storage for dev/test — mirrors RedisVectorSource's execute_query interface.

    Stores docs in a plain dict and computes KNN via cosine distance with numpy.
    No Redis required.
    """

    def __init__(self, name: str = "memory_vector", properties: dict | None = None):
        super().__init__(name, properties=properties or {})
        self.logger = logging.getLogger(self.__class__.__name__)
        # index_name -> {"collection": str, "dim": int, "metric": str}
        self._indices: dict[str, dict] = {}
        # collection -> {doc_id: doc_dict}
        self._store: dict[str, dict[str, dict]] = {}

    # ---------- DataSource interface (stubs — not relevant for registry search) ----------

    def fetch_source_stats(self) -> dict:
        return {"total_docs": sum(len(c) for c in self._store.values())}

    def fetch_databases(self) -> list[str]:
        return list(self._store.keys())

    def fetch_database_collections(self, database: str) -> list[str]:
        return list(self._store.get(database, {}).keys())

    def fetch_collection_stats(self, database, collection, entities=None, relations=None, sample_limit=None) -> dict:
        return {"num_docs": len(self._store.get(collection, {}))}

    # ---------- cosine distance ----------

    def _cosine_distance(self, a, b) -> float:
        va = np.asarray(a, dtype=np.float32)
        vb = np.asarray(b, dtype=np.float32)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))

    # ---------- filter parsing ----------

    def _apply_filter(self, docs: dict[str, dict], filter_expr: str) -> dict[str, dict]:
        """Supports '*' (all) and '@id:{doc_id}' (exact ID match)."""
        if not filter_expr or filter_expr.strip() == "*":
            return docs

        match = re.match(r"@id:\{(.+)\}", filter_expr.strip())
        if match:
            doc_id = match.group(1)
            filtered = {k: v for k, v in docs.items() if k == doc_id}
            return filtered

        self.logger.warning(f"MemoryVectorSource: unsupported filter '{filter_expr}' — returning all docs")
        return docs

    # ---------- execute_query ----------

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        if not isinstance(query, dict):
            raise Exception("MemoryVectorSource expects query as a dict")

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
            self._store.setdefault(coll, {})
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
            self._store.setdefault(coll, {})[doc_id] = doc
            return "OK"

        if op == "VECTOR.DELETE":
            coll = query.get("collection")
            doc_id = query.get("id")
            if not coll or not doc_id:
                raise Exception("VECTOR.DELETE requires collection and id")
            self._store.get(coll, {}).pop(doc_id, None)
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
            filter_expr: str = query.get("filter", "*")

            coll = self._indices[index_name]["collection"]
            docs = self._store.get(coll, {})
            docs = self._apply_filter(docs, filter_expr)

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
