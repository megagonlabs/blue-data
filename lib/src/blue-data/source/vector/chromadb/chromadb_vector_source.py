from __future__ import annotations

import logging

import chromadb

from source.vector.vector_source import VectorSource


class ChromaDBVectorSource(VectorSource):
    """ChromaDB vector source — persistent or ephemeral via chromadb client."""

    def __init__(self, name: str, path: str | None = None, properties: dict | None = None):
        super().__init__(name, properties=properties or {})
        self.logger = logging.getLogger(self.__class__.__name__)
        self._client = (
            chromadb.PersistentClient(path=path) if path else chromadb.EphemeralClient()
        )
        # index_name -> {"collection": str, "embedding_field": str}
        self._indices: dict[str, dict] = {}

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        if not isinstance(query, dict):
            raise Exception("ChromaDBVectorSource expects query as a dict")

        op = query.get("op", "").upper()

        if op == "VECTOR.CREATE_INDEX":
            index_name = query.get("index")
            coll = query.get("collection")
            if not index_name or not coll:
                raise Exception("VECTOR.CREATE_INDEX requires index and collection")
            metric = query.get("distance_metric", "COSINE").lower()
            chroma_metric = {"cosine": "cosine", "l2": "l2", "ip": "ip"}.get(metric, "cosine")
            self._client.get_or_create_collection(
                name=coll,
                metadata={"hnsw:space": chroma_metric},
            )
            self._indices[index_name] = {
                "collection": coll,
                "embedding_field": query.get("embedding_field", "embedding"),
            }
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
            embedding = doc[embedding_field]
            # ChromaDB metadata values must be str, int, float, or bool
            metadata = {
                k: v for k, v in doc.items()
                if k != embedding_field and isinstance(v, (str, int, float, bool))
            }
            chroma_coll = self._client.get_or_create_collection(coll)
            chroma_coll.upsert(ids=[doc_id], embeddings=[embedding], metadatas=[metadata])
            return "OK"

        if op == "VECTOR.DELETE":
            coll = query.get("collection")
            doc_id = query.get("id")
            if not coll or not doc_id:
                raise Exception("VECTOR.DELETE requires collection and id")
            chroma_coll = self._client.get_or_create_collection(coll)
            chroma_coll.delete(ids=[doc_id])
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
            score_alias = query.get("score_alias") or query.get("score_field", "score")
            return_fields: list[str] = list(query.get("return_fields") or [])

            coll = self._indices[index_name]["collection"]
            chroma_coll = self._client.get_or_create_collection(coll)

            response = chroma_coll.query(
                query_embeddings=[query_vector],
                n_results=k,
                include=["distances", "metadatas"],
            )

            ids = response.get("ids", [[]])[0]
            distances = response.get("distances", [[]])[0]
            metadatas = response.get("metadatas", [[]])[0]

            results = []
            for doc_id, dist, meta in zip(ids, distances, metadatas or []):
                row: dict = {"id": doc_id, score_alias: dist}
                if return_fields:
                    for field in return_fields:
                        if field != score_alias and field in (meta or {}):
                            row[field] = meta[field]
                else:
                    row.update(meta or {})
                results.append(row)

            return results

        raise Exception(f"Unsupported vector operation: {op}")
