from __future__ import annotations

import re

import numpy as np

from blue_data.source.vector.vector_source import VectorSource


class MemoryVectorSource(VectorSource):
    """In-memory vector storage for dev/test — mirrors RedisVectorSource's execute_query interface.

    Stores docs in a plain dict and computes KNN via cosine distance with numpy.
    No Redis required.
    """

    def __init__(self, name: str = "memory_vector", embedding_fn=None, properties: dict | None = None):
        super().__init__(name, embedding_fn=embedding_fn, properties=properties or {})
        self._indices: dict[str, dict] = {}
        self._store: dict[str, dict[str, dict]] = {}

    def _initialize_connection_properties(self) -> None:
        conn = self.properties.get("connection", {})
        conn.setdefault("protocol", "vector/memory")
        self.properties["connection"] = conn

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

    @staticmethod
    def _unescape_tag(value: str) -> str:
        return re.sub(r'\\(.)', r'\1', value)

    def _apply_one_clause(self, docs: dict[str, dict], clause: str) -> dict[str, dict]:
        clause = clause.strip()

        # Legacy: @id:{doc_id} — filter by store key
        id_match = re.match(r"@id:\{(.+)\}", clause)
        if id_match:
            doc_id = self._unescape_tag(id_match.group(1))
            return {k: v for k, v in docs.items() if k == doc_id}

        # TAG filter: @field:{value}
        tag_match = re.match(r"@(\w+):\{([^}]*)\}", clause)
        if tag_match:
            field = tag_match.group(1)
            value = self._unescape_tag(tag_match.group(2))
            return {k: v for k, v in docs.items() if str(v.get(field, "")) == value}

        # NUMERIC filter: @field:[lo hi]
        num_match = re.match(r"@(\w+):\[(\S+) (\S+)\]", clause)
        if num_match:
            field = num_match.group(1)
            lo_str, hi_str = num_match.group(2), num_match.group(3)
            lo = float("-inf") if lo_str == "-inf" else float(lo_str)
            hi = float("inf") if hi_str in ("+inf", "inf") else float(hi_str)
            return {
                k: v for k, v in docs.items()
                if field in v and lo <= float(v[field]) <= hi
            }

        self.logger.warning(f"MemoryVectorSource: unsupported filter clause '{clause}' — ignored")
        return docs

    def _apply_filter(self, docs: dict[str, dict], filter_expr: str) -> dict[str, dict]:
        """Apply a Redis Search-style filter expression to the in-memory store.

        Supports:
            ``*``                         — return all docs
            ``@field:{value}``            — TAG exact match (unescapes backslash escapes)
            ``@field:[lo hi]``            — NUMERIC range (-inf / +inf accepted)
            ``(@clause1) (@clause2) …``   — AND of multiple clauses
            ``@id:{doc_id}``              — legacy key-based match
        """
        if not filter_expr or filter_expr.strip() == "*":
            return docs

        expr = filter_expr.strip()

        # Split combined filters: "(@a:{x}) (@b:[1 5])" → ["@a:{x}", "@b:[1 5]"]
        if expr.startswith("("):
            clauses = [part.strip() for part in re.split(r"\) \(", expr.strip("()"))]
        else:
            clauses = [expr]

        result = docs
        for clause in clauses:
            result = self._apply_one_clause(result, clause)
        return result

    # ---------- index introspection ----------

    def list_indexes(self) -> list[dict]:
        result = []
        for idx_name, cfg in self._indices.items():
            coll = cfg["collection"]
            result.append({
                "index":      idx_name,
                "collection": coll,
                "dim":        cfg["dim"],
                "metric":     cfg.get("metric", "COSINE"),
                "doc_count":  len(self._store.get(coll, {})),
            })
        return result

    def fetch_index_info(self, index_name: str) -> dict:
        cfg = self._indices.get(index_name)
        if not cfg:
            return {}
        coll = cfg["collection"]
        docs = self._store.get(coll, {})
        fields: list[str] = []
        for doc in list(docs.values())[:1]:
            fields = [k for k in doc if k != "embedding"]
        return {
            "index":      index_name,
            "collection": coll,
            "dim":        cfg["dim"],
            "metric":     cfg.get("metric", "COSINE"),
            "doc_count":  len(docs),
            "fields":     fields,
        }

    def fetch_index_sample(self, index_name: str, k: int = 3) -> list[dict]:
        cfg = self._indices.get(index_name)
        if not cfg:
            return []
        coll = cfg["collection"]
        docs = self._store.get(coll, {})
        result = []
        for doc_id, doc in list(docs.items())[:k]:
            row = {"id": doc_id}
            row.update({field: val for field, val in doc.items() if field != "embedding"})
            result.append(row)
        return result

    # ---------- primitive operations ----------

    def create_index(self, index_name: str, collection: str, dim: int, distance_metric: str = "COSINE", extra_fields: list | None = None) -> str:
        self._indices[index_name] = {
            "collection": collection,
            "dim": int(dim),
            "metric": distance_metric,
        }
        self._store.setdefault(collection, {})
        return "OK"

    def upsert(self, collection: str, doc_id: str, doc: dict, embedding_field: str = "embedding") -> str:
        if embedding_field not in doc:
            raise Exception(f"VECTOR.UPSERT requires doc with '{embedding_field}' field")
        self._store.setdefault(collection, {})[doc_id] = doc
        return "OK"

    def delete(self, collection: str, doc_id: str) -> int:
        # Return the number of documents actually removed (0 or 1), matching the
        # VectorSource contract and RedisVectorSource — not 1 unconditionally, which
        # made callers report deletions of documents that were never stored.
        store = self._store.get(collection)
        if store is not None and doc_id in store:
            del store[doc_id]
            return 1
        return 0

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
