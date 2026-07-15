class DataSource:
    """Base abstraction for all Blue data sources."""

    content_type: str = "tabular"

    def __init__(self, name: str, properties: dict | None = None):
        self.name = name
        self.properties = properties or {}

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
        """Format *schema* as text for an LLM prompt. Override per dialect."""
        return "(no schema available)"

    def _build_nl_prompt(self, query: str, schema_text: str) -> str:
        """Build the full LLM prompt from *query* and formatted *schema_text*. Override per dialect."""
        return query

    def _extract_native_query(self, raw: str):
        """Extract the native query from raw LLM output. Override per dialect."""
        return raw or None

    def translate_nl_to_native_query(self, query: str, schema: dict | None, llm_fn):
        """Translate a natural language *query* to the source's native query language.

        Calls ``_format_schema_for_nl``, ``_build_nl_prompt``, ``llm_fn``, and
        ``_extract_native_query`` in sequence. Subclasses override the hook methods
        rather than this method.

        Returns the native query (str or dict depending on dialect), or ``None``
        if the LLM returns an empty response.
        """
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

        Uses ``translate_nl_to_native_query`` to produce the dialect-specific query,
        then passes it to ``execute_query``. Subclasses that need a different
        execution shape (e.g. wrapping a filter in an op dict) override this method.

        Parameters:
            query: Natural language query string.
            database: Target database name.
            collection: Target collection/schema name.
            schema: Schema dict with ``entities`` and ``relations`` keys,
                used to ground the LLM translation prompt.
            llm_fn: Callable ``(prompt: str) -> str`` backed by an LLM. Required.
            optional_properties: Extra driver-specific options.
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
        collection: str,
        database: str = "default",
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