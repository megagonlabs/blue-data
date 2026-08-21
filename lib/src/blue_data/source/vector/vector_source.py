from __future__ import annotations

from abc import ABC, abstractmethod

from blue_data.source.source import DataSource


class VectorSource(DataSource, ABC):
    """Base class for vector data sources."""

    def __init__(self, name: str, embedding_fn=None, properties: dict | None = None):
        super().__init__(name, properties=properties)
        self._embedding_fn = embedding_fn

    # ---------- primitive operations ----------

    @abstractmethod
    def create_index(
        self,
        index_name: str,
        collection: str,
        dim: int,
        distance_metric: str = "COSINE",
        extra_fields: list | None = None,
    ) -> str:
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
                extra_fields=query.get("extra_fields"),
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

    # ---------- index introspection (override per backend) ----------

    def list_indexes(self) -> list[dict]:
        """List all available vector indexes with their configuration."""
        return []

    def fetch_index_info(self, index_name: str) -> dict:
        """Return configuration and stats for *index_name*: collection, dim, metric, doc_count, fields."""
        return {}

    def fetch_index_sample(self, index_name: str, k: int = 3) -> list[dict]:
        """Return up to *k* sample documents from *index_name* (embedding field excluded)."""
        return []

    # ---------- NL tool loop ----------

    def get_nl_tools(self, database: str | None = None, collection: str | None = None) -> list[dict]:
        return [
            {
                "name": "list_indexes",
                "description": (
                    "List all available vector indexes with their configuration "
                    "(collection, dimension, distance metric, document count)."
                ),
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "get_index_info",
                "description": (
                    "Get detailed information about a specific vector index: "
                    "collection name, dimension, distance metric, document count, and field names."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "string", "description": "Index name"},
                    },
                    "required": ["index"],
                },
            },
            {
                "name": "get_sample_docs",
                "description": (
                    "Retrieve a small sample of documents from an index to understand "
                    "the document structure and available fields."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "string", "description": "Index name"},
                        "k": {"type": "integer", "description": "Number of sample documents (default 3)"},
                    },
                    "required": ["index"],
                },
            },
            {
                "name": "search_similar",
                "description": (
                    "Perform a semantic similarity search. Pass a natural language text query — "
                    "the source embeds it and returns the k most similar documents. "
                    "Optionally filter by field values using filter expressions "
                    "(TAG: '@field:{value}', NUMERIC: '@field:[lo hi]')."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "index":  {"type": "string", "description": "Index name to search"},
                        "query":  {"type": "string", "description": "Natural language search query text"},
                        "k":      {"type": "integer", "description": "Number of results to return (default 5)"},
                        "filter": {"type": "string", "description": "Optional filter expression"},
                        "return_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Fields to include in results (omit for all fields)",
                        },
                    },
                    "required": ["index", "query"],
                },
            },
        ]

    def execute_nl_tool(
        self,
        name: str,
        tool_input: dict,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ):
        if name == "list_indexes":
            return self.list_indexes()

        if name == "get_index_info":
            return self.fetch_index_info(tool_input["index"])

        if name == "get_sample_docs":
            return self.fetch_index_sample(tool_input["index"], k=int(tool_input.get("k", 3)))

        if name == "search_similar":
            props = optional_properties or {}
            embedding_fn = props.get("embedding_fn") or self._embedding_fn
            if embedding_fn is None:
                raise ValueError("search_similar requires an embedding function")
            query_vector = embedding_fn(tool_input["query"])
            return self.knn(
                index_name=tool_input["index"],
                query_vector=query_vector,
                k=int(tool_input.get("k", 5)),
                score_alias="score",
                return_fields=list(tool_input.get("return_fields") or []),
                filter_expr=tool_input.get("filter", "*"),
            )

        raise ValueError(f"Unknown vector tool: {name!r}")

    def _build_nl_tools_system_prompt(
        self, database: str | None = None, collection: str | None = None
    ) -> str:
        return (
            f"You are a data assistant with access to vector indexes in '{self.name}'. "
            "Use list_indexes to discover available indexes, "
            "get_index_info and get_sample_docs to understand their structure, "
            "then search_similar to find relevant documents by semantic similarity. "
            "Always list indexes first if you do not know what is available. "
            "Return the final answer as plain text, including relevant fields from the search results."
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
