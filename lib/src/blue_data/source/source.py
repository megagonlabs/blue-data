import inspect
import json
import logging
import os
from contextlib import contextmanager


class DataSource:
    """Base abstraction for all Blue data sources."""

    # Op names (for dict/JSON-op sources) this source serves, split by whether they
    # change data. Read-only is deny-by-default (#237): DataRegistry.execute_query runs
    # a dict or JSON op without optional_properties["commit"] only when its op is in
    # _READ_OPS; an op in _WRITE_OPS, or one not declared at all, needs commit, so a
    # source that forgets an op loses read-only access to it rather than gaining
    # unguarded writes. Declare every op in exactly one set. A dict query without an
    # "op" key counts as the op None. Plain SQL strings are not classified here;
    # SQLSource.execute_query guards them itself. #206
    _READ_OPS: frozenset = frozenset()
    _WRITE_OPS: frozenset = frozenset()

    # Property keys that describe only the running process, not the source's
    # reconstructible configuration. DataRegistry.register_source drops these before
    # persisting, so a source the registry rebuilds in another process gets the class
    # default rather than the registering process's value. For example, a UserSource
    # declares {"console"}: a source registered with console=True from an interactive
    # script must not be rebuilt with console=True inside a stdio MCP server or an API
    # process, where a clarification prompt would corrupt the protocol stream or block a
    # request on the server's own stdin. Keys are matched at the top level of the stored
    # properties. #250
    _transient_properties: frozenset = frozenset()

    def __init__(self, name: str, properties: dict | None = None):
        if properties is None:
            properties = {}
        self.name = name
        self._initialize(properties=properties)
        self._start()

    def _query_requires_commit(self, query) -> bool:
        """True unless *query* is a read per ``_READ_OPS``. Classifies a dict op or a
        JSON-encoded object string (the form MCP/REST may pass through); any other
        query (a plain SQL string, ``None``) is left to the source's own guard."""
        if isinstance(query, str):
            stripped = query.strip()
            if not stripped.startswith("{"):
                return False
            try:
                query = json.loads(stripped)
            except (ValueError, TypeError):
                return False
        if not isinstance(query, dict):
            return False
        op = query.get("op")
        if op is None:
            return None not in self._READ_OPS
        return not isinstance(op, str) or op.upper() not in self._READ_OPS

    # ---------- initialization chain ----------

    def _initialize(self, properties=None):
        self._initialize_properties()
        self._update_properties(properties=properties)
        self._initialize_logger()

    def _initialize_properties(self):
        self.properties = {}
        self._initialize_connection_properties()

    def _initialize_connection_properties(self):
        self.properties["connection"] = {"protocol": "default"}

    def _update_properties(self, properties=None):
        if not properties:
            return
        for key, value in properties.items():
            if isinstance(value, dict) and isinstance(self.properties.get(key), dict):
                self.properties[key] = self._deep_merge(self.properties[key], value)
            else:
                self.properties[key] = value

    def _deep_merge(self, base, update):
        result = dict(base)
        for k, v in update.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _initialize_logger(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    # ---------- lifecycle ----------

    def _start(self):
        self._start_connection()
        self.logger.info("Started source %s", self.name)

    def _stop(self):
        self._stop_connection()
        self.logger.info("Stopped source %s", self.name)

    def _start_connection(self):
        connection = self._resolve_connection_env_refs(self.properties["connection"])
        self.connection = self._connect(**connection)

    @staticmethod
    def _resolve_connection_env_refs(connection):
        """Resolve ``<key>_env`` references (e.g. ``password_env``) against the
        environment and strip the reference, returning a COPY passed to ``_connect``.

        Doing this once in the base means every source — not just SQL — can keep a
        secret out of its persisted record and still connect, whether it is built
        directly with ``password_env`` or rebuilt by the registry (#267). A stored
        reference holds an env-var NAME, never the secret, which is why the registry
        sanitizer preserves ``*_env`` keys. An explicit non-empty value wins; an empty
        or default one (e.g. the ``password=""`` sources set) does not mask the
        reference (#239). The reference is always dropped so it never reaches a driver
        as an unknown connection option (#207). ``self.properties`` is left untouched,
        so the live source keeps the reference rather than a resolved literal."""
        if not isinstance(connection, dict):
            return connection
        resolved = dict(connection)
        for key in [k for k in resolved if isinstance(k, str) and k.endswith("_env")]:
            ref = resolved.pop(key)
            base = key[: -len("_env")]
            if base and resolved.get(base) in (None, "") and isinstance(ref, str):
                value = os.environ.get(ref)
                if value is not None:
                    resolved[base] = value
        return resolved

    def _stop_connection(self):
        self._disconnect()

    def _connect(self, **connection):
        return None

    def _disconnect(self):
        return None

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

    # ---------- transactions ----------

    def begin_transaction(self, database: str) -> str:
        raise NotImplementedError(f"{type(self).__name__} does not support transactions")

    def commit_transaction(self, transaction_id: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not support transactions")

    def rollback_transaction(self, transaction_id: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not support transactions")

    def get_transaction_operations(self, transaction_id: str) -> list[dict]:
        raise NotImplementedError(f"{type(self).__name__} does not support transactions")

    def list_transactions(self, database: str | None = None) -> list[str]:
        raise NotImplementedError(f"{type(self).__name__} does not support transactions")

    @contextmanager
    def transaction(self, database: str):
        """Context manager: begin on enter, commit on clean exit, rollback on exception."""
        transaction_id = self.begin_transaction(database)
        try:
            yield transaction_id
        except Exception:
            self.rollback_transaction(transaction_id)
            raise
        else:
            self.commit_transaction(transaction_id)

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

    def create_database(
        self, database: str, properties: dict | None = None, overwrite: bool = False
    ) -> dict:
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

    # Per-entity / per-relation detail. Defaults derive from the bulk
    # ``fetch_database_collection_entities``/``...relations`` so a source that
    # only implements the bulk calls still answers the registry's granular
    # sync methods instead of raising AttributeError.
    def fetch_database_collection_entity_metadata(
        self, database: str, collection: str, entity: str
    ) -> dict:
        return {}

    def fetch_database_collection_entity_attributes(
        self, database: str, collection: str, entity: str
    ) -> dict:
        entity_obj = self.fetch_database_collection_entities(database, collection).get(entity, {})
        return entity_obj.get("contents", {}).get("attributes", {})

    def fetch_database_collection_relation_metadata(
        self, database: str, collection: str, relation: str
    ) -> dict:
        return {}

    def fetch_database_collection_relation_attributes(
        self, database: str, collection: str, relation: str
    ) -> dict:
        relation_obj = self.fetch_database_collection_relations(database, collection).get(relation, {})
        return relation_obj.get("contents", {}).get("attributes", {})

    def create_database_collection(
        self,
        database: str,
        collection: str,
        properties: dict | None = None,
        overwrite: bool = False,
    ) -> dict:
        return {}

    # ---------- entity / relation ----------
    def create_database_collection_entity(
        self,
        database: str,
        collection: str,
        entity: str,
        properties: dict | None = None,
        overwrite: bool = False,
    ) -> dict:
        return {}

    def create_database_collection_relation(
        self,
        database: str,
        collection: str,
        relation: str,
        properties: dict | None = None,
        overwrite: bool = False,
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
        and ignore *llm_fn*. Returns ``None`` when *llm_fn* is absent (default
        LLM path) or the LLM returns an empty response.
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
        read_only: bool = True,
    ) -> list[dict]:
        """Translate *query* from natural language and execute it.

        With *read_only* (the default) any ``commit`` is stripped, so a
        model-generated write is rejected by the source's execute_query guard.
        Pass ``read_only=False`` plus ``commit`` to opt into writes.

        Calls ``translate_nl_to_native_query`` to produce the dialect-specific
        query, then passes it to ``execute_query``.  Returns ``[]`` when
        translation yields nothing.

        Override this method (not ``translate_nl_to_native_query``) only when
        the execution shape differs from a plain ``execute_query`` call — for
        example, MongoDB wraps the filter in a ``FIND`` op dict.  Sources that
        only need a different *translation* strategy (including rule-based
        translation that does not require *llm_fn*) should override
        ``translate_nl_to_native_query`` instead.

        Parameters:
            query:              Natural language query string.
            database:           Target database name.
            collection:         Target collection / schema name.
            schema:             Schema dict (``entities``, ``relations``) used to
                                ground the LLM prompt.  Built by DataRegistry.
            llm_fn:             ``(prompt: str) -> str`` backed by an LLM.
                                Optional — the default implementation returns
                                ``None`` when absent; rule-based overrides may
                                ignore it entirely.
            optional_properties: Extra driver-specific options passed through to
                                ``execute_query``.
        """
        native_query = self.translate_nl_to_native_query(query, schema, llm_fn)
        if not native_query:
            return []
        if read_only and self._is_write_native_query(native_query):
            raise ValueError(
                "Natural-language query translated to a write operation. "
                "Pass read_only=False to allow writes."
            )
        props = dict(optional_properties or {})
        if read_only:
            props.pop("commit", None)
        return self.execute_query(
            native_query,
            database=database,
            collection=collection,
            optional_properties=props,
        )

    def _is_write_native_query(self, native_query) -> bool:
        """Whether *native_query* mutates data. Defaults to the registry's guard: a
        dict/JSON op not in ``_READ_OPS`` is a write (#237); a plain string is not —
        SQL sources rely on the execute_query commit guard, and dialects whose NL
        output can carry writes (e.g. Cypher) override this to detect them."""
        return self._query_requires_commit(native_query)

    # ---------- tool-based nl2q ----------

    def get_nl_tools(self, database: str | None = None, collection: str | None = None) -> list[dict]:
        """Return Anthropic-format tool definitions for this source.

        Override to add or replace tools for a specific source dialect.
        """
        return [
            {
                "name": "list_databases",
                "description": "List available databases in this data source.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "list_collections",
                "description": "List collections or tables in a database.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name"},
                    },
                    "required": ["database"],
                },
            },
            {
                "name": "get_schema",
                "description": "Get the schema (entities and attributes) for a collection.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                    },
                    "required": ["database", "collection"],
                },
            },
            {
                "name": "get_metadata",
                "description": "Get metadata (row count, size, etc.) for a collection.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                    },
                    "required": ["database", "collection"],
                },
            },
            {
                "name": "execute_query",
                "description": "Execute a native query against the data source and return results.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Native query string"},
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_sample",
                "description": "Get a sample of rows from a table/entity along with its total row count.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                        "entity": {"type": "string", "description": "Table or entity name"},
                        "sample_size": {"type": "integer", "description": "Number of rows to sample (default 10)"},
                    },
                    "required": ["database", "entity"],
                },
            },
            {
                "name": "get_column_stats",
                "description": "Get statistics for a specific column: distinct count, min, max, null count, and sample values.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                        "entity": {"type": "string", "description": "Table or entity name"},
                        "column": {"type": "string", "description": "Column name"},
                    },
                    "required": ["database", "entity", "column"],
                },
            },
            {
                "name": "get_relations",
                "description": "Get foreign key relationships for a collection.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string"},
                        "collection": {"type": "string"},
                    },
                    "required": ["database"],
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
        read_only: bool = True,
    ):
        """Dispatch a single tool call by name and return the result.

        Host-pinned *database*/*collection* override model-supplied tool input,
        and with *read_only* (the default) the execute_query tool drops ``commit``
        so a model-generated write is rejected by the source's execute_query guard.
        """
        db = database if database is not None else tool_input.get("database")
        coll = collection if collection is not None else tool_input.get("collection")

        if name == "list_databases":
            return self.fetch_databases()
        if name == "list_collections":
            return self.fetch_database_collections(db)
        if name == "get_schema":
            entities = self.fetch_database_collection_entities(db, coll)
            relations = self.fetch_database_collection_relations(db, coll)
            return {"entities": entities, "relations": relations}
        if name == "get_metadata":
            return self.fetch_database_collection_metadata(db, coll)
        if name == "execute_query":
            props = dict(optional_properties or {})
            if read_only:
                props.pop("commit", None)
            return self.execute_query(
                tool_input["query"],
                database=db,
                collection=coll,
                optional_properties=props,
            )
        if name == "get_sample":
            # fetch_entity_stats signatures vary across sources — only pass
            # row_sample_size to implementations that declare it (or **kwargs).
            params = inspect.signature(self.fetch_entity_stats).parameters
            extra = {}
            if "row_sample_size" in params or any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
            ):
                extra["row_sample_size"] = tool_input.get("sample_size", 10)
            return self.fetch_entity_stats(db, coll, tool_input["entity"], **extra)
        if name == "get_column_stats":
            return self.fetch_property_stats(
                db,
                coll,
                tool_input["entity"],
                tool_input["column"],
            )
        if name == "get_relations":
            return self.fetch_database_collection_relations(db, coll)
        raise ValueError(f"Unknown tool: {name!r}")

    def _build_nl_tools_system_prompt(
        self, database: str | None = None, collection: str | None = None
    ) -> str:
        parts = [f"You are a data assistant for the '{self.name}' data source."]
        if database:
            parts.append(f"The target database is '{database}'.")
        if collection:
            parts.append(f"The target collection is '{collection}'.")
        parts.append(
            "Use the available tools to explore the data and answer the user's question. "
            "Return the final answer as plain text."
        )
        return " ".join(parts)

    def _read_only_tool_names(self) -> set[str]:
        """NL tool names safe to run under read_only. Defaults to every tool this
        source exposes (today all are reads); a source that adds write tools
        overrides this to exclude them."""
        return {t.get("name") for t in self.get_nl_tools() if isinstance(t, dict)}

    def execute_query_nl_tools(
        self,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        llm_fn=None,
        optional_properties: dict | None = None,
        max_iterations: int = 10,
        extra_tools: list[dict] | None = None,
        extra_tool_fn=None,
        read_only: bool = True,
        max_sample_size: int | None = None,
    ) -> list[dict]:
        """Tool-based NL2Q: drive an LLM tool loop to answer *query*.

        ``llm_fn`` must accept ``(messages, tools, system=None)`` and return a
        response dict with::

            {
                "stop_reason": "tool_use" | "end_turn",
                "content": [
                    {"type": "text", "text": "..."},
                    {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
                ]
            }

        ``extra_tools`` / ``extra_tool_fn`` let callers (e.g. DataRegistry) inject
        additional tools into the loop without subclassing. ``extra_tool_fn`` receives
        ``(tool_name, tool_input)`` and should raise ``ValueError`` for tools it does
        not own so dispatch falls through to ``execute_nl_tool``.

        Returns the rows from the last ``execute_query`` tool call, or wraps the
        LLM's final text answer as ``[{"answer": text}]``.
        """
        if llm_fn is None:
            return []

        tools = self.get_nl_tools(database=database, collection=collection)
        if extra_tools:
            tools = tools + extra_tools
        read_only_tool_names = self._read_only_tool_names()
        if extra_tools:
            read_only_tool_names = read_only_tool_names | {
                t.get("name") for t in extra_tools if isinstance(t, dict)
            }
        system = self._build_nl_tools_system_prompt(database, collection)
        messages = [{"role": "user", "content": query}]
        last_query_result = None

        for _ in range(max_iterations):
            response = llm_fn(messages, tools, system=system)
            content = response.get("content", [])
            messages.append({"role": "assistant", "content": content})

            if response.get("stop_reason") != "tool_use":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        return last_query_result if last_query_result is not None else [{"answer": text}]
                return last_query_result or []

            tool_results = []
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tool_name = block["name"]
                tool_input = block.get("input", {})
                # Pin host scope and enforce read-only at the loop level so every
                # source's execute_nl_tool (incl. overrides) is covered unchanged.
                if database is not None:
                    tool_input = {**tool_input, "database": database}
                if collection is not None:
                    tool_input = {**tool_input, "collection": collection}
                call_props = optional_properties
                if read_only and optional_properties:
                    call_props = {k: v for k, v in optional_properties.items() if k != "commit"}
                if max_sample_size is not None and isinstance(tool_input.get("sample_size"), int):
                    tool_input = {**tool_input, "sample_size": min(tool_input["sample_size"], max_sample_size)}
                tool_id = block["id"]
                if read_only and tool_name not in read_only_tool_names:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": f"Error: tool '{tool_name}' is not permitted in read-only mode",
                    })
                    continue
                try:
                    if extra_tool_fn is not None:
                        try:
                            result = extra_tool_fn(tool_name, tool_input)
                        except ValueError:
                            result = self.execute_nl_tool(
                                tool_name, tool_input,
                                database=database, collection=collection,
                                optional_properties=call_props,
                            )
                    else:
                        result = self.execute_nl_tool(
                            tool_name, tool_input,
                            database=database, collection=collection,
                            optional_properties=call_props,
                        )
                    if tool_name == "execute_query" and isinstance(result, list):
                        last_query_result = result
                except Exception as e:
                    result = {"error": str(e)}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(result),
                })

            messages.append({"role": "user", "content": tool_results})

        return last_query_result or []

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
        """Import rows from *source* into this DataSource.

        Subclasses override this to implement the actual write logic.
        The base implementation is a no-op and returns ``{}``.

        Contract for subclasses:
        - Read rows by calling ``source.execute_query(None, collection=collection)``.
        - Write those rows into the local store identified by *database* / *entity*.
        - Respect *mode*: ``"append"`` adds to existing data; ``"overwrite"``
          replaces it entirely before writing.
        - Return a dict with at least ``{"status": "success", "rows_imported": n}``.

        Args:
            source: The DataSource to pull rows from.
            database: Target database within this source.
            collection: Collection name used to query the *source* side.
                Note: ``collection`` and ``entity`` refer to different levels of
                the hierarchy — ``collection`` is the schema/directory, ``entity``
                is the specific table/file to write. For backends where these are
                the same concept (e.g. ``FileSource``), ``entity`` is ignored.
            entity: Specific table or entity to write into on the target side.
                Required for SQL targets; ignored by file-based targets.
            mode: ``"append"`` or ``"overwrite"``.
            options: Backend-specific options (e.g. output format for files).
        """
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

    def fetch_relation_stats(
        self,
        database: str,
        collection: str,
        relation: str,
    ) -> dict | None:
        return None