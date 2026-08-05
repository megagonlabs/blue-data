class DataSource:
    """Base abstraction for all Blue data sources."""

    content_type: str = "tabular"

    def __init__(self, name: str, properties: dict | None = None):
        self.name = name
        self.properties = properties or {}

    @classmethod
    def instantiate(cls, full_class_path: str, *args, **kwargs) -> "DataSource":
        """Instantiate a DataSource subclass by its fully-qualified class path.

        Example:
            DataSource.instantiate(
                "blue_data.source.graph.neo4j.neo4j_graph_source.NEO4JSource",
                "my_source",
                properties={...},
            )
        """
        import importlib
        module_path, class_name = full_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        source_cls = getattr(module, class_name)
        return source_cls(*args, **kwargs)

    # ---------- source ----------
    def fetch_metadata(self) -> dict:
        return {}

    def fetch_schema(self) -> dict:
        return {}

    # ---------- database ----------
    def fetch_databases(self) -> list[str]:
        return []

    def fetch_database_metadata(self, database: str) -> dict:
        return {}

    def fetch_database_schema(self, database: str) -> dict:
        return {}

    def create_database(self, database: str, properties: dict | None = None) -> dict:
        return {}

    # ---------- collection ----------
    def fetch_database_collections(self, database: str) -> list[str]:
        return []

    def fetch_database_collection_metadata(
        self,
        database: str,
        collection: str,
    ) -> dict:
        return {}

    def fetch_database_collection_entities(
        self,
        database: str,
        collection: str,
    ) -> dict:
        return {}

    def fetch_database_collection_relations(
        self,
        database: str,
        collection: str,
    ) -> dict:
        return {}

    def create_database_collection(
        self,
        database: str,
        collection: str,
        properties: dict | None = None,
    ) -> dict:
        return {}

    # ---------- entity / relation ----------
    def create_database_collection_entity(
        self,
        database: str,
        collection: str,
        entity: str,
        properties: dict | None = None,
    ) -> dict:
        return {}

    def create_database_collection_relation(
        self,
        database: str,
        collection: str,
        relation: str,
        properties: dict | None = None,
    ) -> dict:
        return {}

    # ---------- query ----------
    def execute_query(
        self,
        query,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        return []

    def _format_schema_for_nl(self, schema: dict | None) -> str:
        """Render *schema* as plain text for inclusion in an LLM prompt.

        Override per dialect — SQL renders table/column lists, Neo4j renders
        node/relationship lists. The base implementation returns a placeholder.
        """
        return "(no schema available)"

    def _build_nl_prompt(self, query: str, schema_text: str) -> str:
        """Compose the full LLM prompt from *query* and the formatted *schema_text*.

        Override per dialect to add dialect-specific instructions (e.g. "write a
        SQL SELECT", "write a Cypher MATCH"). The base implementation returns
        *query* unchanged (useful for testing).
        """
        return query

    def _extract_native_query(self, raw: str):
        """Clean raw LLM output into a runnable native query string or dict.

        Override per dialect to strip markdown fences (` ```sql ... ``` `),
        extract JSON objects, etc. Returns ``None`` for empty/unparseable input.
        """
        return raw or None

    def translate_nl_to_native_query(self, query: str, schema: dict | None, llm_fn):
        """Translate a natural language *query* to this source's native query language.

        Default LLM-backed pipeline (all steps are overridable per dialect)::

            _format_schema_for_nl(schema)   → schema_text
            _build_nl_prompt(query, schema_text) → prompt
            llm_fn(prompt)                  → raw LLM output
            _extract_native_query(raw)      → native query (str or dict)

        To plug in rule-based or DSL translation, override this method directly
        and ignore *llm_fn*. Returns ``None`` when *llm_fn* is absent or the LLM
        returns an empty response.
        """
        if llm_fn is None:
            return None
        schema_text = self._format_schema_for_nl(schema)
        prompt = self._build_nl_prompt(query, schema_text)
        raw = llm_fn(prompt)
        return self._extract_native_query(raw) if raw else None

    def execute_query_nl(
        self,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        schema: dict | None = None,
        llm_fn=None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Translate *query* from natural language and execute it.

        Calls ``translate_nl_to_native_query`` to produce the dialect-specific
        query, then passes it to ``execute_query``.  Returns ``[]`` when
        *llm_fn* is absent or translation yields nothing.

        Override this method (not ``translate_nl_to_native_query``) only when
        the execution shape differs from a plain ``execute_query`` call — for
        example, MongoDB wraps the filter in a ``FIND`` op dict.  Sources that
        only need a different *translation* strategy should override
        ``translate_nl_to_native_query`` instead.

        Parameters:
            query:              Natural language query string.
            database:           Target database name.
            collection:         Target collection / schema name.
            schema:             Schema dict (``entities``, ``relations``) used to
                                ground the LLM prompt.  Built by DataRegistry.
            llm_fn:             ``(prompt: str) -> str`` backed by an LLM.
                                Optional — returns ``[]`` when absent.
            optional_properties: Extra driver-specific options passed through to
                                ``execute_query``.
        """
        if llm_fn is None:
            return []
        native_query = self.translate_nl_to_native_query(query, schema, llm_fn)
        if not native_query:
            return []
        return self.execute_query(
            native_query,
            database=database,
            collection=collection,
            optional_properties=optional_properties,
        )

    # ---------- import ----------
    def import_data(
        self,
        source: "DataSource",
        database: str = "default",
        collection: str = "default",
        entity: str | None = None,
        mode: str = "append",
        options: dict | None = None,
    ) -> dict:
        return {}

    # ---------- stats ----------
    def fetch_source_stats(self) -> dict | None:
        return None

    def fetch_database_stats(self, database: str) -> dict | None:
        return None

    def fetch_collection_stats(
        self,
        database: str,
        collection: str,
        entities: list | None = None,
        relations: list | None = None,
        sample_limit: int | None = None,
    ) -> dict | None:
        return None

    def fetch_entity_stats(
        self,
        database: str,
        collection: str,
        entity: str,
    ) -> dict | None:
        return None

    def fetch_property_stats(
        self,
        database: str,
        collection: str,
        entity: str,
        property_name: str,
        sample_limit: int | None = None,
    ) -> dict | None:
        return None