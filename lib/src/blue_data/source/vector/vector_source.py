from __future__ import annotations

from abc import ABC, abstractmethod

from blue_data.source.source import DataSource


class VectorSource(DataSource, ABC):
    """Base class for vector data sources."""

    content_type: str = "vector"

    def __init__(self, name: str, embedding_fn=None, properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._embedding_fn = embedding_fn

    # ---------- primitive operations ----------

    @abstractmethod
    def create_index(self, index_name: str, collection: str, dim: int, distance_metric: str = "COSINE") -> str:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, collection: str, doc_id: str, doc: dict, embedding_field: str = "embedding") -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, collection: str, doc_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    # ---------- query ----------

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        """Execute a compound vector operation.

        query must be a dict with:
            op – one of:
                "VECTOR.CREATE_INDEX"  index, collection, dim, distance_metric (opt)
                "VECTOR.UPSERT"        collection, id, doc, embedding_field (opt)
                "VECTOR.DELETE"        collection, id
                "VECTOR.KNN"           index, vector/embedding, k (opt), field (opt),
                                       score_alias (opt), return_fields (opt), filter (opt)
        """
        if not isinstance(query, dict):
            raise ValueError(
                "VectorSource.execute_query expects query as a dict with 'op' and operation-specific fields"
            )

        op = (query.get("op") or "").upper()

        if op == "VECTOR.CREATE_INDEX":
            return self.create_index(
                index_name=query["index"],
                collection=query["collection"],
                dim=int(query["dim"]),
                distance_metric=query.get("distance_metric", "COSINE"),
            )

        if op == "VECTOR.UPSERT":
            return self.upsert(
                collection=query["collection"],
                doc_id=query["id"],
                doc=query["doc"],
                embedding_field=query.get("embedding_field", "embedding"),
            )

        if op == "VECTOR.DELETE":
            return self.delete(
                collection=query["collection"],
                doc_id=query["id"],
            )

        if op == "VECTOR.KNN":
            query_vector = (
                query.get("vector")
                or query.get("embedding")
                or query.get("query_vector")
                or query.get("query_embedding")
            )
            if query_vector is None:
                raise ValueError(
                    "VECTOR.KNN requires a query vector "
                    "(key: vector, embedding, query_vector, or query_embedding)"
                )
            return self.knn(
                index_name=query["index"],
                query_vector=query_vector,
                k=int(query.get("k", 5)),
                embedding_field=query.get("field") or query.get("vector_field", "embedding"),
                score_alias=query.get("score_alias") or query.get("score_field", "score"),
                return_fields=list(query.get("return_fields") or []),
                filter_expr=query.get("filter", "*"),
            )

        raise ValueError(
            f"Unsupported VectorSource operation: {op!r}. "
            "Supported: VECTOR.CREATE_INDEX, VECTOR.UPSERT, VECTOR.DELETE, VECTOR.KNN"
        )

    # ---------- NL query ----------

    def execute_query_nl(
        self,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        schema: dict | None = None,
        llm_fn=None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Embed *query* and run KNN — no LLM required.

        Embedding function priority: ``optional_properties["embedding_fn"]`` >
        ``self._embedding_fn`` (set at construction or injected by DataRegistry).
        The index to search defaults to *collection*; override via
        ``optional_properties["index"]``.

        Returns ``[]`` when no embedding function is available.
        """
        props = optional_properties or {}
        embedding_fn = props.get("embedding_fn") or self._embedding_fn
        if embedding_fn is None:
            return []

        index = props.get("index") or collection
        if index is None:
            return []

        query_vector = embedding_fn(query)
        return self.knn(
            index_name=index,
            query_vector=query_vector,
            k=int(props.get("k", 5)),
            embedding_field=props.get("embedding_field", "embedding"),
            score_alias=props.get("score_alias", "score"),
            return_fields=list(props.get("return_fields") or []),
            filter_expr=props.get("filter", "*"),
        )
