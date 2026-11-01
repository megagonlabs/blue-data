from __future__ import annotations

import copy
import os
import re
from urllib.parse import urlsplit, urlunsplit

from blue_data.registry.registry import Registry
from blue_data.registry.search.registry_search import RegistrySearch

from blue_data.source.source import DataSource


from blue_data.registry.enrichment.semantic_types import SemanticTypeInferencer


# Case-insensitive substrings (matched against the key with separators removed) that
# mark a value as a secret. Broader than an exact list, so db_password, sasl_password,
# passphrase, auth_token, aws_secret_access_key and an Authorization header key are all
# caught (#212). ``key`` is intentionally NOT a bare substring — it would strip
# legitimate non-secret config such as partition_key / keyspace / aws_access_key_id; the
# real key-shaped secrets (api_key, apikey, private_key) are covered explicitly.
_SECRET_KEY_SUBSTRINGS = (
    "pass", "pwd", "secret", "token", "credential", "authorization", "apikey", "privatekey",
)


def _is_secret_key(key) -> bool:
    """True when a dict key names a secret and its value must not be persisted."""
    if not isinstance(key, str):
        return False
    lower = key.lower()
    # Preserve ``<name>_env`` reference keys: they hold an env-var NAME, not the secret,
    # and connect_source needs them to reconnect (#100/#207).
    if lower.endswith("_env"):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", lower)
    return any(sub in normalized for sub in _SECRET_KEY_SUBSTRINGS)


# scheme://user:password@host  — backstop for a password containing '/' (which truncates
# the authority urlsplit parses). Greedy to the last '@' so it also spans '@' in the pw.
_URI_PASSWORD_RE = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)(?P<user>[^:/\s@]*):[^\s]*@"
)

# key=value secrets in ODBC/JDBC-style connection strings (Pwd=…, Password=…, Token=…).
_KV_SECRET_RE = re.compile(
    r"(?i)\b(?P<key>password|passwd|pwd|secret|token|api[_-]?key)\b(?P<sep>\s*=\s*)[^;]*"
)


def _strip_uri_userinfo(value: str) -> str:
    """Drop passwords embedded in a string value so they aren't persisted: URI userinfo
    and ODBC/JDBC ``k=v;`` connection strings. Handles passwords containing '/' or '@'
    (urlsplit splits on the last '@'; a regex backstop covers authorities a '/' in the
    password would otherwise truncate). #100 #212"""
    # 1) Well-formed URLs: rebuild without the password, keeping user/host/port/path/query.
    try:
        parts = urlsplit(value)
    except ValueError:
        parts = None
    if parts is not None and parts.password is not None:
        user = parts.username or ""
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        netloc = f"{user}@{host}" if user else host
        value = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    # 2) Backstop: a '/' in the password truncates the authority urlsplit sees, so strip
    #    scheme://user:…@ directly (greedy to the last '@').
    value = _URI_PASSWORD_RE.sub(lambda m: f"{m.group('scheme')}{m.group('user')}@", value)
    # 3) ODBC/JDBC connection-string secrets: keep the key, drop the value.
    value = _KV_SECRET_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}", value)
    return value


def _sanitize_value(value):
    if isinstance(value, dict):
        return {
            k: _sanitize_value(v)
            for k, v in value.items()
            if not _is_secret_key(k)
        }
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, str):
        return _strip_uri_userinfo(value)
    return value


def _sanitize_properties(properties: dict) -> dict:
    """Return a copy of *properties* with credential keys removed at every depth and
    passwords stripped from connection-URI userinfo (#100). Reference keys such as
    ``password_env`` (an env-var NAME, not the secret) are preserved so connect_source
    can resolve them after a restart."""
    return _sanitize_value(properties)


def _resolve_credential_references(properties: dict) -> dict:
    """Resolve ``<key>_env`` references against the environment so a persisted source
    can reconnect: ``{"password_env": "PGPASSWORD"}`` sets ``password`` from
    ``os.environ["PGPASSWORD"]``. Only the reference (a name) is ever stored; the
    secret is read from the environment at connect time (#100)."""
    def resolve(obj):
        if isinstance(obj, dict):
            out = {k: resolve(v) for k, v in obj.items()}
            for key in list(out):
                if isinstance(key, str) and key.endswith("_env") and isinstance(out[key], str):
                    target = key[: -len("_env")]
                    if target and target not in out:
                        env_value = os.environ.get(out[key])
                        if env_value is not None:
                            out[target] = env_value
                    # Drop the reference so it is never passed on to a DB driver, which
                    # rejects an unknown connection option like 'password_env' (#207).
                    del out[key]
            return out
        if isinstance(obj, list):
            return [resolve(v) for v in obj]
        return obj

    return resolve(properties)


class DataRegistry(Registry):
    """Registry for managing data sources and their hierarchical metadata.

    Extends Registry with typed helpers that map the path convention
    ``source → database → collection → entity/relation → attribute``, plus
    sync, stats-collection, and semantic-enrichment operations.
    """

    def __init__(
        self,
        name: str = "DATA_REGISTRY",
        store=None,
        vector_source=None,
        embedding_fn=None,
        rebuild: bool = False,
        index_name: str = "registry_index",
        vector_dim: int = 1536,
        hybrid_config: dict | None = None,
        metadata_enricher=None,
    ):
        super().__init__(name=name, store=store)
        self.sources: dict[str, DataSource] = {}
        self.semantic_type_inferencer = SemanticTypeInferencer()
        self._rebuild = rebuild
        self.metadata_enricher = metadata_enricher
        self.search_engine = RegistrySearch(
            registry=self,
            vector_source=vector_source,
            embedding_fn=embedding_fn,
            index_name=index_name,
            vector_dim=vector_dim,
            hybrid_config=hybrid_config,
        )

    # ---------- rebuild hooks ----------

    def _on_record_changed(self, record: dict, rebuild: bool | None = None) -> None:
        should = self._rebuild if rebuild is None else rebuild
        if should:
            self.search_engine.index_record(record)

    def _on_record_deleted(self, name: str, type: str, scope: str, rebuild: bool | None = None) -> None:
        should = self._rebuild if rebuild is None else rebuild
        if should:
            self.search_engine.remove_record_from_index(name, type, scope)

    def register_source(self, source: DataSource) -> None:
        """Register a DataSource and add a corresponding top-level registry record.

        Credentials (password, token, api_key, etc.) are stripped from the stored
        record so they are never persisted to the registry store or returned by any
        read tool.  The live DataSource object in self.sources retains full credentials.

        Properties the source declares in ``_transient_properties`` describe only the
        registering process (e.g. a UserSource's ``console``) and are dropped before
        storing, so a source the registry rebuilds in another process gets the class
        default rather than this process's value. #250
        """
        self.sources[source.name] = source

        cls = type(source)
        safe_properties = _sanitize_properties(source.properties)
        for key in getattr(source, "_transient_properties", frozenset()):
            safe_properties.pop(key, None)
        safe_properties["_class"] = f"{cls.__module__}.{cls.__qualname__}"
        self.register_record(
            name=source.name,
            type="source",
            scope="/",
            description=f"{source.name} data source",
            properties=safe_properties,
        )

    def register_unavailable_source(self, name, class_path=None, properties=None, error=None):
        """Register a source *record* (no live object) for a configured source that
        could not be constructed/connected, so it still appears in list_sources marked
        unavailable rather than failing the whole registry. Credentials are stripped as
        in register_source. #106"""
        safe_properties = _sanitize_properties(properties or {})
        if class_path:
            safe_properties["_class"] = class_path
        safe_properties["status"] = "unavailable"
        if error is not None:
            safe_properties["error"] = str(error)
        self.register_record(
            name=name,
            type="source",
            scope="/",
            description=f"{name} data source (unavailable)",
            properties=safe_properties,
        )

    def get_source(self, name: str) -> DataSource | None:
        """Return the live DataSource object for *name*, or None if not registered."""
        return self.sources.get(name)

    def list_sources(self) -> list[str]:
        """Return the names of all registered sources — both live (in-process)
        and those persisted in the registry store but not yet instantiated.

        Platform hosts (MCP/REST/CLI) load a persisted registry with an empty
        live ``self.sources``; reading only the dict hid every persisted source.
        """
        names = list(self.sources.keys())
        seen = set(names)
        for record in self.get_sources():
            name = record.get("name") if isinstance(record, dict) else None
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    
    def execute_query(
        self,
        source: str,
        query,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ):
        """Execute *query* against the named source, raising ValueError if it is not registered."""

        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        # Read-only by default (design/14), deny-by-default for dict/JSON ops: without
        # an explicit commit only an op the source declares in _READ_OPS runs; a write
        # or undeclared op is refused on every surface (CLI, REST, MCP). #206, #237
        optional_properties = optional_properties or {}
        if not optional_properties.get("commit") and source_obj._query_requires_commit(query):
            raise ValueError(
                "Write operation requires optional_properties={'commit': True}; "
                "queries are read-only by default."
            )

        return source_obj.execute_query(
            query=query,
            database=database,
            collection=collection,
            optional_properties=optional_properties,
        )

    def import_data(
        self,
        source: str,
        target: str,
        database: str = "default",
        collection: str = "default",
        entity: str | None = None,
        mode: str = "append",
        options: dict | None = None,
    ) -> dict:
        """Import rows from *source* into *target* via their registered DataSource objects.

        The transfer is pull-based: the target DataSource reads rows from the source
        by calling ``source.execute_query(None, collection=collection)``.

        Args:
            source: Registered name of the DataSource to read from.
            target: Registered name of the DataSource to write into.
            database: Target database (e.g. the ``.db`` filename for SQLite).
            collection: Identifies which collection to read on the source side.
                For ``FileSource`` this is the file stem (``"customers"`` →
                ``customers.csv``). For SQL sources it is the schema name.
            entity: Target table/entity name on the destination side. Required
                for SQL targets (``SQLiteDBSource``, etc.) because the source
                ``collection`` concept (schema) differs from the target entity
                concept (table). Ignored by ``FileSource``, which derives the
                output filename from ``collection``. Omitting this for a SQL
                target raises ``ValueError``.
            mode: ``"append"`` (default) adds rows to existing data.
                ``"overwrite"`` clears the target table/file first.
            options: Backend-specific options passed to the target's
                ``import_data`` implementation (e.g. ``{"format": "parquet"}``
                for ``FileSource``).

        Raises:
            ValueError: If either *source* or *target* is not registered or
                connectable, or if the target implementation requires *entity*
                and it was not provided.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        target_obj = self.connect_source(target)
        if target_obj is None:
            raise ValueError(f"Target not registered or connectable: {target}")

        return target_obj.import_data(
            source=source_obj,
            collection=collection,
            database=database,
            entity=entity,
            mode=mode,
            options=options,
        )

    def export_data(
        self,
        source: str,
        path: str,
        collection: str = "default",
        database: str | None = None,
        query=None,
        fmt: str | None = None,
    ) -> dict:
        """Export rows from *source*/*collection* directly to a file.

        Args:
            source: Registered DataSource name to read from.
            path: Output file path. Format is inferred from the extension
                  (csv, json, jsonl, parquet) when *fmt* is omitted.
            collection: Collection (table/file) to export.
            database: Database to query; uses the source default when omitted.
            query: Optional filter passed to ``execute_query``. ``None``
                   returns all rows; a dict performs equality filtering.
            fmt: Force output format (``"csv"``, ``"json"``, ``"jsonl"``,
                 ``"parquet"``). Overrides extension inference.
        """
        import json as _json
        import os

        import pandas as pd

        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        rows = source_obj.execute_query(
            query=query,
            database=database,
            collection=collection,
        )

        if fmt is None:
            ext = os.path.splitext(path)[1].lstrip(".")
            fmt = ext if ext in ("csv", "json", "jsonl", "parquet") else "csv"

        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

        df = pd.DataFrame(rows)

        if fmt == "csv":
            df.to_csv(path, index=False)
        elif fmt == "json":
            df.to_json(path, orient="records", indent=2)
        elif fmt == "jsonl":
            with open(path, "w") as f:
                for record in df.to_dict(orient="records"):
                    f.write(_json.dumps(record) + "\n")
        elif fmt == "parquet":
            df.to_parquet(path, index=False)
        else:
            raise ValueError(
                f"Unsupported export format: {fmt!r}. Use csv, json, jsonl, or parquet."
            )

        return {
            "status": "success",
            "rows_written": len(df),
            "path": os.path.abspath(path),
            "format": fmt,
        }

    def execute_query_nl(
        self,
        source: str,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Translate *query* from natural language and execute it against *source*.

        For SQL/graph sources, pulls schema context and the LLM callable from the
        metadata enricher and delegates to the source's ``execute_query_nl``.
        For vector sources, injects the registry's embedding function so the query
        is embedded and run as KNN — no LLM required.
        Raises ``ValueError`` if the source is not registered or connectable.
        """
        from blue_data.source.vector.vector_source import VectorSource

        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        props = dict(optional_properties or {})

        if isinstance(source_obj, VectorSource):
            embedding_fn = self.search_engine.embedding_fn
            if embedding_fn is not None:
                props.setdefault("embedding_fn", embedding_fn)
            return source_obj.execute_query_nl(
                query=query,
                database=database,
                collection=collection,
                optional_properties=props,
            )

        llm_fn = (
            self.metadata_enricher._llm_fn
            if self.metadata_enricher is not None
            else None
        )

        schema = None
        if database and collection:
            schema = self.build_schema_for_nl(source, database, collection)

        return source_obj.execute_query_nl(
            query=query,
            database=database,
            collection=collection,
            schema=schema,
            llm_fn=llm_fn,
            optional_properties=props,
        )

    def execute_query_nl_tools(
        self,
        source: str,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
        max_iterations: int = 10,
    ) -> list[dict]:
        """Drive a tool-based NL2Q loop against *source*, injecting a registry-aware
        ``get_enriched_metadata`` tool so the LLM can access semantic types,
        descriptions, and value semantics stored in the registry.

        Raises ``ValueError`` if the source is not registered or connectable.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        llm_fn = (
            self.metadata_enricher._llm_fn
            if self.metadata_enricher is not None
            else None
        )

        extra_tools = [
            {
                "name": "get_enriched_metadata",
                "description": (
                    "Get enriched metadata stored in the registry for a table/entity or "
                    "a specific column/attribute: semantic types, descriptions, value "
                    "semantics, domain concepts, and aggregation hints. Use this to "
                    "understand column meaning before writing a query."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string", "description": "Table or entity name"},
                        "attribute": {
                            "type": "string",
                            "description": "Column or attribute name (omit for entity-level metadata)",
                        },
                    },
                    "required": ["entity"],
                },
            }
        ]

        def extra_tool_fn(name, tool_input):
            if name != "get_enriched_metadata":
                raise ValueError(f"Unknown registry tool: {name!r}")
            return self.get_enriched_metadata(
                source, database, collection,
                tool_input["entity"], tool_input.get("attribute"),
            )

        return source_obj.execute_query_nl_tools(
            query=query,
            database=database,
            collection=collection,
            llm_fn=llm_fn,
            optional_properties=optional_properties,
            max_iterations=max_iterations,
            extra_tools=extra_tools,
            extra_tool_fn=extra_tool_fn,
        )

    # Enrichment written directly under record["properties"] by the metadata
    # pipeline. get_enriched_metadata returns all of these (not just "metadata"),
    # so the tool exposes the semantic enrichment its description promises. #82
    _ENRICHMENT_PROPERTY_KEYS = (
        "metadata",
        "value_semantics",
        "semantic_discovery",
        "domain_concept",
        "interpretive_semantics",
        "value_axis",
        "quantitative_vst",
        "safe_aggregation",
        "semantic_role",
        "role_query_constraints",
        "process_vst_role",
        "time_grain_candidates",
        "data_quality",
        # entity-level
        "process_semantics",
        "process_patterns",
        "process_trends",
        "process_operators",
        "process_query_constraints",
        "total_component_measures",
        "derived_metric_candidates",
    )

    def get_enriched_metadata(self, source, database, collection, entity, attribute=None):
        """Return the enrichment stored on an entity/attribute record — value
        semantics, semantic discovery, domain concepts, roles, aggregation hints,
        process semantics, data quality, and ``metadata`` — plus the record
        description. Backs the ``get_enriched_metadata`` NL tool, which previously
        returned only ``properties["metadata"]`` and so hid most enrichment. #82"""
        if attribute:
            record = self.get_source_database_collection_entity_attribute(
                source, database, collection, entity, attribute
            )
        else:
            record = self.get_source_database_collection_entity(
                source, database, collection, entity
            )
        if record is None:
            return {}
        props = record.get("properties", {}) or {}
        result = {k: props[k] for k in self._ENRICHMENT_PROPERTY_KEYS if k in props}
        description = record.get("description")
        if description:
            result["description"] = description
        return result

    def build_schema_for_nl(
        self,
        source: str,
        database: str,
        collection: str,
        include_metadata: bool = False,
    ) -> dict:
        entity_records = self.list_collection_entities(source, database, collection)
        entities = []
        for record in entity_records:
            entity_name = record["name"]
            attr_records = self.list_entity_attributes(source, database, collection, entity_name)
            attributes = {}
            for attr in attr_records:
                attr_name = attr["name"]
                props = attr.get("properties", {})
                info = props.get("info", {})
                col_type = info.get("type", "TEXT") if isinstance(info, dict) else str(info)
                attr_entry: dict = {"type": col_type}
                if include_metadata:
                    vs = props.get("value_semantics")
                    if vs:
                        attr_entry["value_semantics"] = vs
                    meta = props.get("metadata")
                    if meta:
                        attr_entry["metadata"] = meta
                attributes[attr_name] = attr_entry

            entity_entry: dict = {"name": entity_name, "attributes": attributes}
            if include_metadata:
                entity_props = record.get("properties", {})
                process_semantics = entity_props.get("process_semantics")
                if process_semantics:
                    entity_entry["process_semantics"] = process_semantics
                entity_meta = entity_props.get("metadata")
                if entity_meta:
                    entity_entry["metadata"] = entity_meta
            entities.append(entity_entry)

        relation_records = self.list_collection_relations(source, database, collection)
        relations = []
        for record in relation_records:
            props = record.get("properties", {})
            relations.append({
                "name": props.get("name", record["name"]),
                "source": props.get("source", ""),
                "target": props.get("target", ""),
                "properties": props.get("properties", {}),
            })

        return {"entities": entities, "relations": relations}

    # ---------- hierarchy helpers ----------

    def register_source_database(
        self,
        source: str,
        database: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register a database record under the given source."""
        return self.register_record(
            name=database,
            type="database",
            scope=f"/source/{source}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register a collection record under the given source/database."""
        return self.register_record(
            name=collection,
            type="collection",
            scope=f"/source/{source}/database/{database}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register an entity record under the given source/database/collection."""
        return self.register_record(
            name=entity,
            type="entity",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register an attribute record under the given entity."""
        return self.register_record(
            name=attribute,
            type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register a relation record under the given source/database/collection."""
        return self.register_record(
            name=relation,
            type="relation",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        description: str = "",
        properties: dict | None = None,
    ):
        """Register an attribute record under the given relation."""
        return self.register_record(
            name=attribute,
            type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            description=description,
            properties=properties or {},
        )

    def list_source_databases(self, source: str):
        """Return all database records registered under *source*."""
        return self.list_records(
            record_type="database",
            scope=f"/source/{source}",
        )

    def list_database_collections(
        self,
        source: str,
        database: str,
    ):
        """Return all collection records registered under *source/database*."""
        return self.list_records(
            record_type="collection",
            scope=f"/source/{source}/database/{database}",
        )

    def list_collection_entities(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Return all entity records registered under *source/database/collection*."""
        return self.list_records(
            record_type="entity",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
        )

    def list_entity_attributes(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        """Return all attribute records registered under the given entity."""
        return self.list_records(
            record_type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )

    # ---------- hierarchy property helpers ----------

    def get_source_database_property(
        self,
        source: str,
        database: str,
        key: str,
    ):
        """Return the value of property *key* on the given database record."""
        return self.get_record_property(
            database,
            "database",
            f"/source/{source}",
            key,
        )

    def set_source_database_property(
        self,
        source: str,
        database: str,
        key: str,
        value,
    ):
        """Set property *key* to *value* on the given database record."""
        return self.set_record_property(
            database,
            "database",
            f"/source/{source}",
            key,
            value,
        )

    def get_source_database_collection_property(
        self,
        source: str,
        database: str,
        collection: str,
        key: str,
    ):
        """Return the value of property *key* on the given collection record."""
        return self.get_record_property(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            key,
        )

    def set_source_database_collection_property(
        self,
        source: str,
        database: str,
        collection: str,
        key: str,
        value,
        rebuild: bool | None = None,
    ):
        """Set property *key* to *value* on the given collection record."""
        return self.set_record_property(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            key,
            value,
            rebuild=rebuild,
        )

    def get_source_database_collection_entity_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        key: str,
    ):
        """Return the value of property *key* on the given entity record."""
        return self.get_record_property(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
        )

    def set_source_database_collection_entity_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        key: str,
        value,
        rebuild: bool | None = None,
    ):
        """Set property *key* to *value* on the given entity record."""
        return self.set_record_property(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
            value,
            rebuild=rebuild,
        )

    def get_source_database_collection_entity_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        key: str,
    ):
        """Return the value of property *key* on the given entity attribute record."""
        return self.get_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            key,
        )

    def set_source_database_collection_entity_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        key: str,
        value,
        rebuild: bool | None = None,
    ):
        """Set property *key* to *value* on the given entity attribute record."""
        return self.set_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            key,
            value,
            rebuild=rebuild,
        )

    # ---------- hierarchy description helpers ----------

    def get_source_database_description(
        self,
        source: str,
        database: str,
    ):
        """Return the description of the given database record."""
        return self.get_record_description(
            database,
            "database",
            f"/source/{source}",
        )

    def set_source_database_description(
        self,
        source: str,
        database: str,
        description: str,
        rebuild: bool | None = None,
    ):
        """Set the description of the given database record."""
        return self.set_record_description(
            database,
            "database",
            f"/source/{source}",
            description,
            rebuild=rebuild,
        )

    def get_source_database_collection_description(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Return the description of the given collection record."""
        return self.get_record_description(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
        )

    def set_source_database_collection_description(
        self,
        source: str,
        database: str,
        collection: str,
        description: str,
        rebuild: bool | None = None,
    ):
        """Set the description of the given collection record."""
        return self.set_record_description(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            description,
            rebuild=rebuild,
        )

    def get_source_database_collection_entity_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        """Return the description of the given entity record."""
        return self.get_record_description(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
        )

    def set_source_database_collection_entity_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str,
        rebuild: bool | None = None,
    ):
        """Set the description of the given entity record."""
        return self.set_record_description(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            description,
            rebuild=rebuild,
        )

    def get_source_database_collection_entity_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        """Return the description of the given entity attribute record."""
        return self.get_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )

    def set_source_database_collection_entity_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str,
        rebuild: bool | None = None,
    ):
        """Set the description of the given entity attribute record."""
        return self.set_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description,
            rebuild=rebuild,
        )


    def sync_all(self, recursive: bool = False):
        for source in self.list_sources():
            self.sync_source(source, recursive=recursive)
        
    # ---------- sync helpers ----------

    def sync_source(self, source: str, recursive: bool = False):
        """Reconcile the registry's database list with what the live source reports.

        Adds databases that are new, removes ones that have disappeared, and
        with ``recursive=True`` descends into every database to sync its
        collections as well (otherwise only new/merged databases are descended).
        Also stores any top-level source metadata returned by the source.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        metadata = source_obj.fetch_metadata()
        if metadata:
            self.set_record_property(source, "source", "/", "metadata", metadata)

        fetched_databases = set(source_obj.fetch_databases())
        registry_databases = {
            record["name"]
            for record in self.list_source_databases(source)
        }

        adds = fetched_databases - registry_databases
        removes = registry_databases - fetched_databases
        merges = fetched_databases & registry_databases

        for database in adds:
            self.register_source_database(
                source=source,
                database=database,
            )

        for database in removes:
            self.deregister_source_database(
                source=source,
                database=database,
            )

        databases_to_sync = fetched_databases if recursive else adds | merges

        for database in databases_to_sync:
            self.sync_source_database(
                source=source,
                database=database,
                source_obj=source_obj,
                recursive=recursive,
            )


    def sync_source_database(
        self,
        source: str,
        database: str,
        source_obj=None,
        recursive: bool = False,
    ):
        """Reconcile the registry's collection list for *database* with the live source.

        Mirrors the add/remove/merge logic of ``sync_source`` one level deeper.
        Pass *source_obj* to skip the registry lookup when already available.
        With ``recursive=True`` every collection is descended; otherwise only
        new and existing (merged) collections are synced.
        """
        if source_obj is None:
            source_obj = self.get_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        metadata = source_obj.fetch_database_metadata(database)
        if metadata:
            self.set_source_database_property(
                source,
                database,
                "metadata",
                metadata,
            )

        fetched_collections = set(
            source_obj.fetch_database_collections(database)
        )

        registry_collections = {
            record["name"]
            for record in self.list_database_collections(source, database)
        }

        adds = fetched_collections - registry_collections
        removes = registry_collections - fetched_collections
        merges = fetched_collections & registry_collections

        for collection in adds:
            self.register_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        for collection in removes:
            self.deregister_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        collections_to_sync = fetched_collections if recursive else adds | merges

        for collection in collections_to_sync:
            self.sync_source_database_collection(
                source=source,
                database=database,
                collection=collection,
                source_obj=source_obj,
            )

    def sync_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        source_obj=None,
    ):
        """Reconcile entities, their attributes, relations, and relation attributes for *collection*.

        For each object type the method computes adds/removes/merges and
        calls the appropriate register/deregister/update helpers so the registry
        reflects the current live schema of the collection.
        """
        if source_obj is None:
            source_obj = self.get_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        metadata = source_obj.fetch_database_collection_metadata(
            database,
            collection,
        )

        if metadata:
            self.set_source_database_collection_property(
                source,
                database,
                collection,
                "metadata",
                metadata,
            )

        # ---------- entities ----------
        entities = source_obj.fetch_database_collection_entities(
            database,
            collection,
        )

        fetched_entities = set(entities.keys())

        registry_entities = {
            record["name"]
            for record in self.list_collection_entities(
                source,
                database,
                collection,
            )
        }

        entity_adds = fetched_entities - registry_entities
        entity_removes = registry_entities - fetched_entities
        entity_merges = fetched_entities & registry_entities

        for entity_name in entity_adds:
            entity_obj = entities[entity_name]

            self.register_source_database_collection_entity(
                source=source,
                database=database,
                collection=collection,
                entity=entity_name,
                properties=entity_obj.get("properties", {}),
            )

        for entity_name in entity_removes:
            self.deregister_source_database_collection_entity(
                source,
                database,
                collection,
                entity_name,
            )

        for entity_name in entity_adds | entity_merges:
            entity_obj = entities[entity_name]

            self.update_source_database_collection_entity(
                source,
                database,
                collection,
                entity_name,
                properties=entity_obj.get("properties", {}),
            )

            attributes = (
                entity_obj
                .get("contents", {})
                .get("attributes", {})
            )

            fetched_attributes = set(attributes.keys())

            registry_attributes = {
                record["name"]
                for record in self.list_entity_attributes(
                    source,
                    database,
                    collection,
                    entity_name,
                )
            }

            attr_adds = fetched_attributes - registry_attributes
            attr_removes = registry_attributes - fetched_attributes
            attr_merges = fetched_attributes & registry_attributes

            for attr_name in attr_adds:
                self.register_source_database_collection_entity_attribute(
                    source=source,
                    database=database,
                    collection=collection,
                    entity=entity_name,
                    attribute=attr_name,
                    properties=attributes[attr_name],
                )

            for attr_name in attr_removes:
                self.deregister_source_database_collection_entity_attribute(
                    source,
                    database,
                    collection,
                    entity_name,
                    attr_name,
                )

            for attr_name in attr_adds | attr_merges:
                self.update_source_database_collection_entity_attribute(
                    source,
                    database,
                    collection,
                    entity_name,
                    attr_name,
                    properties=attributes[attr_name],
                )

        # ---------- relations ----------
        relations = source_obj.fetch_database_collection_relations(
            database,
            collection,
        )

        fetched_relations = set(relations.keys())

        registry_relations = {
            record["name"]
            for record in self.list_collection_relations(
                source,
                database,
                collection,
            )
        }

        relation_adds = fetched_relations - registry_relations
        relation_removes = registry_relations - fetched_relations
        relation_merges = fetched_relations & registry_relations

        for relation_name in relation_adds:
            relation_obj = relations[relation_name]

            self.register_source_database_collection_relation(
                source=source,
                database=database,
                collection=collection,
                relation=relation_name,
                properties=relation_obj.get("properties", {}),
            )

        for relation_name in relation_removes:
            self.deregister_source_database_collection_relation(
                source,
                database,
                collection,
                relation_name,
            )

        for relation_name in relation_adds | relation_merges:
            relation_obj = relations[relation_name]

            self.update_source_database_collection_relation(
                source,
                database,
                collection,
                relation_name,
                properties=relation_obj.get("properties", {}),
            )

            relation_attributes = (
                relation_obj
                .get("contents", {})
                .get("attributes", {})
            )

            fetched_relation_attributes = set(relation_attributes.keys())

            registry_relation_attributes = {
                record["name"]
                for record in self.get_source_database_collection_relation_attributes(
                    source,
                    database,
                    collection,
                    relation_name,
                )
            } 

            rel_attr_adds = fetched_relation_attributes - registry_relation_attributes
            rel_attr_removes = registry_relation_attributes - fetched_relation_attributes
            rel_attr_merges = fetched_relation_attributes & registry_relation_attributes

            for attr_name in rel_attr_adds:
                self.register_source_database_collection_relation_attribute(
                    source=source,
                    database=database,
                    collection=collection,
                    relation=relation_name,
                    attribute=attr_name,
                    properties=relation_attributes[attr_name],
                )

            for attr_name in rel_attr_removes:
                self.deregister_source_database_collection_relation_attribute(
                    source,
                    database,
                    collection,
                    relation_name,
                    attr_name,
                )

            for attr_name in rel_attr_adds | rel_attr_merges:
                self.update_source_database_collection_relation_attribute(
                    source,
                    database,
                    collection,
                    relation_name,
                    attr_name,
                    properties=relation_attributes[attr_name],
                )
       
        schema = self.get_data_source_schema(
            source,
            database,
            collection,
            format="json",
        )

        if schema and schema != "{}":
            self.set_source_database_collection_property(
                source,
                database,
                collection,
                "schema",
                schema,
            )

    def collect_source_database_stats(
        self,
        source: str,
        database: str,
    ):
        """Fetch stats from the live source for *database* and store them as the ``stats`` property."""
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_database_stats(database)

        if stats:
            self.set_source_database_property(
                source,
                database,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_stats(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Fetch stats for *collection* (passing its registered entities/relations) and persist them."""
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        entities = self.list_collection_entities(source, database, collection)
        relations = self.list_collection_relations(source, database, collection) if hasattr(self, "list_collection_relations") else []

        stats = source_obj.fetch_collection_stats(
            database,
            collection,
            entities,
            relations,
        )

        if stats:
            self.set_source_database_collection_property(
                source,
                database,
                collection,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_entity_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        """Fetch stats for *entity* from the live source and store them as the ``stats`` property."""
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_entity_stats(
            database,
            collection,
            entity,
        )

        if stats:
            self.set_source_database_collection_entity_property(
                source,
                database,
                collection,
                entity,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_entity_attribute_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        sample_limit: int = 10,
    ):
        """Fetch property-level stats (including sample values) for *attribute* and persist them."""
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_property_stats(
            database,
            collection,
            entity,
            attribute,
            sample_limit=sample_limit,
        )

        if stats:
            self.set_source_database_collection_entity_attribute_property(
                source,
                database,
                collection,
                entity,
                attribute,
                "stats",
                stats,
            )

        return stats

    def collect_source_stats(
        self,
        source: str,
        recursive: bool = False,
        sample_limit: int = 10,
    ):
        """Collect and store top-level stats for *source*.

        With ``recursive=True`` descends the full hierarchy (databases →
        collections → entities → attributes), storing stats at each level.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_source_stats()

        if stats:
            self.set_record_property(
                source,
                "source",
                "/",
                "stats",
                stats,
            )

        if recursive:
            for database_record in self.list_source_databases(source):
                database = database_record["name"]

                self.collect_source_database_stats(
                    source,
                    database,
                )

                for collection_record in self.list_database_collections(
                    source,
                    database,
                ):
                    collection = collection_record["name"]

                    self.collect_source_database_collection_stats(
                        source,
                        database,
                        collection,
                    )

                    for entity_record in self.list_collection_entities(
                        source,
                        database,
                        collection,
                    ):
                        entity = entity_record["name"]

                        self.collect_source_database_collection_entity_stats(
                            source,
                            database,
                            collection,
                            entity,
                        )

                        for attribute_record in self.list_entity_attributes(
                            source,
                            database,
                            collection,
                            entity,
                        ):
                            attribute = attribute_record["name"]

                            self.collect_source_database_collection_entity_attribute_stats(
                                source,
                                database,
                                collection,
                                entity,
                                attribute,
                                sample_limit=sample_limit,
                            )

        return stats

    # ---------- data quality ----------

    def compute_attribute_data_quality(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ) -> dict:
        """Compute and store the ``data_quality`` property for *attribute*.

        Reads ``stats`` and ``value_semantics`` from the registry (collecting
        stats on the fly when absent) and writes the result back as
        ``"data_quality"``.
        """
        from blue_data.registry.enrichment.data_quality import compute_attribute_dq

        stats = self.get_source_database_collection_entity_attribute_property(
            source, database, collection, entity, attribute, "stats"
        )
        if not stats:
            stats = self.collect_source_database_collection_entity_attribute_stats(
                source, database, collection, entity, attribute
            )

        value_semantics = self.get_source_database_collection_entity_attribute_property(
            source, database, collection, entity, attribute, "value_semantics"
        )

        dq = compute_attribute_dq(stats or {}, value_semantics)
        self.set_source_database_collection_entity_attribute_property(
            source, database, collection, entity, attribute, "data_quality", dq
        )
        return dq

    def compute_entity_data_quality_summary(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ) -> dict:
        """Aggregate per-attribute DQ into an entity-level ``data_quality_summary``.

        Expects ``compute_attribute_data_quality`` to have already run for each
        attribute; missing attributes are skipped silently.

        Also computes ``misplaced_value_rate`` (cross-column) and writes the per-
        attribute breakdown back into each attribute's ``data_quality`` property.
        """
        from blue_data.registry.enrichment.data_quality import (
            compute_entity_dq_summary,
            compute_misplaced_rates,
        )

        attribute_dq: dict[str, dict]       = {}
        attribute_semantics: dict[str, dict] = {}
        attribute_stats: dict[str, dict]     = {}

        for attr_record in self.list_entity_attributes(source, database, collection, entity):
            attr_name = attr_record["name"]
            dq = self.get_source_database_collection_entity_attribute_property(
                source, database, collection, entity, attr_name, "data_quality"
            )
            if dq:
                attribute_dq[attr_name] = dq

            sem = self.get_source_database_collection_entity_attribute_property(
                source, database, collection, entity, attr_name, "value_semantics"
            )
            if sem:
                attribute_semantics[attr_name] = sem

            st = self.get_source_database_collection_entity_attribute_property(
                source, database, collection, entity, attr_name, "stats"
            )
            if st:
                attribute_stats[attr_name] = st

        entity_stats = self.get_source_database_collection_entity_property(
            source, database, collection, entity, "stats"
        )
        row_samples = (entity_stats or {}).get("row_samples")

        summary = compute_entity_dq_summary(
            attribute_dq,
            row_samples=row_samples,
            attribute_semantics=attribute_semantics or None,
            attribute_stats=attribute_stats or None,
        )

        # Write misplaced_value_rate back to each attribute's data_quality property
        misplaced_map: dict | None = summary.get("misplaced_value_rate")
        if misplaced_map and attribute_dq:
            for attr_name, rate in misplaced_map.items():
                if attr_name in attribute_dq:
                    updated_dq = dict(attribute_dq[attr_name])
                    updated_dq["misplaced_value_rate"] = rate
                    self.set_source_database_collection_entity_attribute_property(
                        source, database, collection, entity, attr_name, "data_quality", updated_dq
                    )

        self.set_source_database_collection_entity_property(
            source, database, collection, entity, "data_quality_summary", summary
        )
        return summary

    def compute_source_data_quality(
        self,
        source: str,
        recursive: bool = True,
    ) -> None:
        """Compute DQ metrics across the full source hierarchy.

        Walks databases → collections → entities → attributes, calling
        ``compute_attribute_data_quality`` per attribute and then
        ``compute_entity_data_quality_summary`` per entity.
        Skips silently on missing stats rather than raising.
        """
        if not recursive:
            return

        for database_record in self.list_source_databases(source):
            database = database_record["name"]
            for collection_record in self.list_database_collections(source, database):
                collection = collection_record["name"]
                for entity_record in self.list_collection_entities(source, database, collection):
                    entity = entity_record["name"]
                    for attr_record in self.list_entity_attributes(
                        source, database, collection, entity
                    ):
                        self.compute_attribute_data_quality(
                            source, database, collection, entity, attr_record["name"]
                        )
                    self.compute_entity_data_quality_summary(
                        source, database, collection, entity
                    )

    def list_collection_relations(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Return all relation records registered under *source/database/collection*."""
        return self.list_records(
            record_type="relation",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
        )

    def enrich_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        rebuild: bool = False,
    ):
        """Infer and store semantic type information for *attribute*.

        Reads existing stats (or collects them on the fly) to obtain sample
        values, runs them through the ``SemanticTypeInferencer``, and writes
        the result as the ``value_semantics`` property on the attribute record.

        The deterministic base layer never clobbers a richer LLM-sourced
        ``value_semantics`` (``source == "llm"``) on a ``rebuild=False`` pass (#98).
        """
        existing = self.get_source_database_collection_entity_attribute_property(
            source, database, collection, entity, attribute, "value_semantics",
        )
        if not rebuild and isinstance(existing, dict) and existing.get("source") == "llm":
            return existing

        stats = self.get_source_database_collection_entity_attribute_property(
            source,
            database,
            collection,
            entity,
            attribute,
            "stats",
        )

        if not stats:
            stats = self.collect_source_database_collection_entity_attribute_stats(
                source,
                database,
                collection,
                entity,
                attribute,
            )

        values = stats.get("sample_values", [])
        semantic_info = self.semantic_type_inferencer.infer(values)

        self.set_source_database_collection_entity_attribute_property(
            source,
            database,
            collection,
            entity,
            attribute,
            "value_semantics",
            semantic_info,
        )

        return semantic_info

    def enrich_source(self, source: str, rebuild: bool = False):
        """Run deterministic semantic type enrichment on every attribute across all databases and collections.

        With ``rebuild=False`` an attribute that already carries an LLM-sourced
        ``value_semantics`` is left untouched so the base layer does not overwrite
        a richer VSI result (#98)."""
        for database_record in self.list_source_databases(source):
            database = database_record["name"]

            for collection_record in self.list_database_collections(source, database):
                collection = collection_record["name"]

                for entity_record in self.list_collection_entities(source, database, collection):
                    entity = entity_record["name"]

                    for attribute_record in self.list_entity_attributes(
                        source, database, collection, entity
                    ):
                        attribute = attribute_record["name"]

                        self.enrich_source_database_collection_entity_attribute(
                            source,
                            database,
                            collection,
                            entity,
                            attribute,
                            rebuild=rebuild,
                        )

    def enrich_source_metadata(
        self,
        source: str,
        recursive: bool = True,
        rebuild: bool = False,
        on_progress=None,
    ):
        """Run the full metadata enrichment pipeline via the injected ``metadata_enricher``.

        Always runs ``enrich_source`` first as the deterministic base layer — this
        ensures ``value_semantics`` is set on every attribute using
        ``SemanticTypeInferencer`` (pattern-based, no LLM).  The ``metadata_enricher``
        then builds on top: if an ``llm_fn`` is configured the LLM-based enrichments
        (VSI, SDI, DCM, IVS, description generation, link validation) run and overwrite
        the base-layer types with richer ones; if not, only the deterministic
        enrichments (semantic-links, process-semantics, quantitative-VST, value-axis,
        semantic-roles) run — they can now read the VSI set in the base layer.

        ``on_progress``, when supplied, is called after each entity completes::

            def on_progress(entity_name, database, collection, done, total):
                ...
        """
        self.enrich_source(source, rebuild=rebuild)
        if self.metadata_enricher is not None:
            # Count total entities upfront so on_progress can report X/N.
            total = 0
            if on_progress is not None:
                for db in self.list_source_databases(source):
                    for coll in self.list_database_collections(source, db.get("name")):
                        total += len(self.list_collection_entities(source, db.get("name"), coll.get("name")))
            self.metadata_enricher.collect_source_metadata(
                self, source, recursive=recursive, rebuild=rebuild,
                on_progress=on_progress, total=total,
            )

    # ---------- source record helpers ----------

    def get_source_record(self, source: str):
        """Return the top-level registry record for *source*."""
        return self.get_record(source, "source", "/")

    def update_source(
        self,
        source: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the top-level source record."""
        return self.update_record(
            source,
            "source",
            "/",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source(self, source: str):
        """Remove *source* from both the live sources dict and the registry."""
        record = self.get_source_record(source)
        self.sources.pop(source, None)
        return self.deregister(record)


    # ---------- database update/deregister/get helpers ----------

    def get_source_database(self, source: str, database: str):
        """Return the registry record for *database* under *source*."""
        return self.get_record(
            database,
            "database",
            f"/source/{source}",
        )

    def update_source_database(
        self,
        source: str,
        database: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given database record."""
        return self.update_record(
            database,
            "database",
            f"/source/{source}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database(self, source: str, database: str):
        """Remove the given database record from the registry."""
        record = self.get_source_database(source, database)
        return self.deregister(record)

    # ---------- collection update/deregister/get helpers ----------

    def get_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Return the registry record for *collection* under *source/database*."""
        return self.get_record(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
        )

    def update_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given collection record."""
        return self.update_record(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        """Remove the given collection record from the registry."""
        record = self.get_source_database_collection(source, database, collection)
        return self.deregister(record)

    # ---------- entity update/deregister/get helpers ----------

    def get_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        """Return the registry record for *entity* under *source/database/collection*."""
        return self.get_record(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
        )

    def update_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given entity record."""
        return self.update_record(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        """Remove the given entity record from the registry."""
        record = self.get_source_database_collection_entity(
            source,
            database,
            collection,
            entity,
        )
        return self.deregister(record)

    # ---------- entity attribute update/deregister/get helpers ----------

    def get_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        """Return the registry record for *attribute* under the given entity."""
        return self.get_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )

    def update_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given entity attribute record."""
        return self.update_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        """Remove the given entity attribute record from the registry."""
        record = self.get_source_database_collection_entity_attribute(
            source,
            database,
            collection,
            entity,
            attribute,
        )
        return self.deregister(record)

    # ---------- create operation helpers ----------

    def create_source_database(
        self,
        source: str,
        database: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        """Create *database* via the live source and register it.

        Returns None (no-op) if the database already exists and *overwrite* is
        False. If *overwrite* is True the existing registry record is removed
        before creation. On success the source is re-synced and any extra
        *properties* are written back to the new record.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database(source, database) and not overwrite:
            return None

        if self.get_source_database(source, database) and overwrite:
            self.deregister_source_database(source, database)

        result = source_obj.create_database(
            database,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source(source, recursive=recursive)

            for key, value in (properties or {}).items():
                self.set_source_database_property(
                    source,
                    database,
                    key,
                    value,
                )

        return result

    def create_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        """Create *collection* via the live source and register it under *database*.

        Follows the same overwrite and post-sync semantics as
        ``create_source_database``.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database_collection(source, database, collection) and not overwrite:
            return None

        if self.get_source_database_collection(source, database, collection) and overwrite:
            self.deregister_source_database_collection(source, database, collection)

        result = source_obj.create_database_collection(
            database,
            collection,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database(
                source,
                database,
                source_obj=source_obj,
                recursive=recursive,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_property(
                    source,
                    database,
                    collection,
                    key,
                    value,
                )

        return result

    def create_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        properties: dict | None = None,
        creation_properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        """Create *entity* via the live source and register it.

        Automatically registers the parent database and collection in the
        registry if they are missing. *creation_properties* are passed to the
        source's create call; *properties* are written back to the registry
        record after a successful sync. Returns None if the entity already
        exists and *overwrite* is False.
        """
        source_obj = self.connect_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        # Ensure parent database exists in registry
        if not self.get_source_database(source, database):
            self.register_source_database(
                source=source,
                database=database,
            )

        # Ensure parent collection exists in registry
        if not self.get_source_database_collection(source, database, collection):
            self.register_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        if self.get_source_database_collection_entity(source, database, collection, entity) and not overwrite:
            return None

        if self.get_source_database_collection_entity(source, database, collection, entity) and overwrite:
            self.deregister_source_database_collection_entity(
                source,
                database,
                collection,
                entity,
            )

        result = source_obj.create_database_collection_entity(
            database,
            collection,
            entity,
            properties=creation_properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database_collection(
                source,
                database,
                collection,
                source_obj=source_obj,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_entity_property(
                    source,
                    database,
                    collection,
                    entity,
                    key,
                    value,
                )

        return result

    def create_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        """Create *relation* via the live source and register it under *collection*.

        Follows the same overwrite and post-sync semantics as
        ``create_source_database``.
        """
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database_collection_relation(source, database, collection, relation) and not overwrite:
            return None

        if self.get_source_database_collection_relation(source, database, collection, relation) and overwrite:
            self.deregister_source_database_collection_relation(
                source,
                database,
                collection,
                relation,
            )

        result = source_obj.create_database_collection_relation(
            database,
            collection,
            relation,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database_collection(
                source,
                database,
                collection,
                source_obj=source_obj,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_relation_property(
                    source,
                    database,
                    collection,
                    relation,
                    key,
                    value,
                )

        return result

    def get_source_database_collection_relation_attributes(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        """Return all attribute records registered under the given relation."""
        return self.list_records(
            record_type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
        )

    # ---------- relation update/deregister/get helpers ----------

    def get_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        """Return the registry record for *relation* under *source/database/collection*."""
        return self.get_record(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
        )


    def update_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given relation record."""
        return self.update_record(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties,
            icon=icon,
        )


    def deregister_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        """Remove the given relation record from the registry."""
        record = self.get_source_database_collection_relation(
            source,
            database,
            collection,
            relation,
        )
        return self.deregister(record)


    # ---------- relation property helpers ----------

    def get_source_database_collection_relation_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        key: str,
    ):
        """Return the value of property *key* on the given relation record."""
        return self.get_record_property(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
        )


    def set_source_database_collection_relation_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        key: str,
        value,
    ):
        """Set property *key* to *value* on the given relation record."""
        return self.set_record_property(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
            value,
        )


    # ---------- relation description helpers ----------

    def get_source_database_collection_relation_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        """Return the description of the given relation record."""
        return self.get_record_description(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
        )


    def set_source_database_collection_relation_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str,
    ):
        """Set the description of the given relation record."""
        return self.set_record_description(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            description,
        )

    # ---------- relation attribute update/deregister/get helpers ----------

    def get_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
    ):
        """Return the registry record for *attribute* under the given relation."""
        return self.get_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
        )


    def update_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        """Update metadata fields on the given relation attribute record."""
        return self.update_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            description=description,
            properties=properties,
            icon=icon,
        )


    def deregister_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
    ):
        """Remove the given relation attribute record from the registry."""
        record = self.get_source_database_collection_relation_attribute(
            source,
            database,
            collection,
            relation,
            attribute,
        )
        return self.deregister(record)

    def get_data_source_schema(
        self,
        source: str,
        database: str,
        collection: str,
        format: str = "dict",
    ):
        source_props = self.get_source_properties(source) or {}
        protocol = source_props.get("connection", {}).get("protocol")

        if protocol == "bn":
            collection_props = self.get_source_database_collection_properties(source, database, collection) or {}
            graph_structure = collection_props.get("graph_structure", {})
            schema = {
                "entities": [],
                "relations": [],
                "graph_structure": graph_structure,
                "node_count": collection_props.get("node_count", len(graph_structure.get("nodes", {}))),
                "edge_count": collection_props.get("edge_count", sum(
                    len(v) for v in graph_structure.get("edges", {}).values()
                )),
            }
        else:
            schema = {
                "entities": self.list_collection_entities(source, database, collection),
                "relations": self.list_collection_relations(source, database, collection),
            }

        if format == "dict":
            return schema

        if format == "json":
            import json
            return json.dumps(schema, indent=2)

        if format == "yaml":
            import yaml
            return yaml.dump(schema)

        return str(schema)

    # ---------- source property / connection helpers ----------

    def get_source_properties(self, source: str):
        return self.get_record_properties(
            source,
            "source",
            "/",
        )


    def get_source_property(self, source: str, key: str):
        return self.get_record_property(
            source,
            "source",
            "/",
            key,
        )


    def set_source_property(self, source: str, key: str, value):
        return self.set_record_property(
            source,
            "source",
            "/",
            key,
            value,
        )


    def delete_source_property(self, source: str, key: str):
        return self.delete_record_property(
            source,
            "source",
            "/",
            key,
        )


    def get_source_connection(self, source: str):
        return self.get_source_property(source, "connection")


    def set_source_connection(self, source: str, connection: dict):
        return self.set_source_property(
            source,
            "connection",
            connection,
        )
    
    def connect_source(self, source: str):
        existing_source = self.get_source(source)
        if existing_source is not None:
            return existing_source

        properties = self.get_source_properties(source)
        if not properties:
            return None

        class_path = properties.get("_class")
        if not class_path:
            raise ValueError(f"Source '{source}' has no '_class' property — cannot instantiate")
        # Resolve any stored <key>_env credential references from the environment so a
        # persisted source reconnects after a restart without the secret on disk (#100).
        properties = _resolve_credential_references(properties)
        from blue_data.source.source import DataSource as _DS
        source_obj = _DS.instantiate(class_path, source, properties=properties)


        self.sources[source] = source_obj
        return source_obj

    def sync_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        source_obj=None,
        recursive: bool = False,
    ):
        if source_obj is None:
            source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        metadata = source_obj.fetch_database_collection_entity_metadata(
            database,
            collection,
            entity,
        )

        if metadata:
            self.update_source_database_collection_entity(
                source,
                database,
                collection,
                entity,
                properties={"metadata": metadata},
            )

        try:
            attributes = source_obj.fetch_database_collection_entity_attributes(
                database,
                collection,
                entity,
            ) or {}
        except AttributeError:
            entity_obj = source_obj.fetch_database_collection_entities(
                database,
                collection,
            ).get(entity, {})
            attributes = (
                entity_obj
                .get("contents", {})
                .get("attributes", {})
            )

        fetched_attributes = set(attributes.keys())

        registry_attributes = {
            record["name"]
            for record in self.list_entity_attributes(
                source,
                database,
                collection,
                entity,
            )
        }

        attr_adds = fetched_attributes - registry_attributes
        attr_removes = registry_attributes - fetched_attributes
        attr_merges = fetched_attributes & registry_attributes

        for attr_name in attr_adds:
            self.register_source_database_collection_entity_attribute(
                source=source,
                database=database,
                collection=collection,
                entity=entity,
                attribute=attr_name,
                properties=attributes[attr_name],
            )

        for attr_name in attr_removes:
            self.deregister_source_database_collection_entity_attribute(
                source,
                database,
                collection,
                entity,
                attr_name,
            )

        for attr_name in attr_adds | attr_merges:
            self.update_source_database_collection_entity_attribute(
                source,
                database,
                collection,
                entity,
                attr_name,
                properties=attributes[attr_name],
            )

    def sync_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        source_obj=None,
        recursive: bool = False,
    ):
        if source_obj is None:
            source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        metadata = source_obj.fetch_database_collection_relation_metadata(
            database,
            collection,
            relation,
        )

        if metadata:
            self.update_source_database_collection_relation(
                source,
                database,
                collection,
                relation,
                properties={"metadata": metadata},
            )

        try:
            attributes = source_obj.fetch_database_collection_relation_attributes(
                database,
                collection,
                relation,
            ) or {}
        except AttributeError:
            relation_obj = source_obj.fetch_database_collection_relations(
                database,
                collection,
            ).get(relation, {})
            attributes = (
                relation_obj
                .get("contents", {})
                .get("attributes", {})
            )

        fetched_attributes = set(attributes.keys())

        registry_attributes = {
            record["name"]
            for record in self.get_source_database_collection_relation_attributes(
                source,
                database,
                collection,
                relation,
            )
        }

        attr_adds = fetched_attributes - registry_attributes
        attr_removes = registry_attributes - fetched_attributes
        attr_merges = fetched_attributes & registry_attributes

        for attr_name in attr_adds:
            self.register_source_database_collection_relation_attribute(
                source=source,
                database=database,
                collection=collection,
                relation=relation,
                attribute=attr_name,
                properties=attributes[attr_name],
            )

        for attr_name in attr_removes:
            self.deregister_source_database_collection_relation_attribute(
                source,
                database,
                collection,
                relation,
                attr_name,
            )

        for attr_name in attr_adds | attr_merges:
            self.update_source_database_collection_relation_attribute(
                source,
                database,
                collection,
                relation,
                attr_name,
                properties=attributes[attr_name],
            )

    # ---------- relation attribute property helpers ----------

    def get_source_database_collection_relation_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        key: str,
    ):
        return self.get_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            key,
        )


    def set_source_database_collection_relation_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            key,
            value,
        )


    # ---------- relation attribute description helpers ----------

    def get_source_database_collection_relation_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
    ):
        return self.get_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
        )


    def set_source_database_collection_relation_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        description: str,
    ):
        return self.set_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            description,
        )
    

    def collect_source_database_collection_relation_stats(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_relation_stats(
            database,
            collection,
            relation,
        )

        if stats:
            self.set_source_database_collection_relation_property(
                source,
                database,
                collection,
                relation,
                "stats",
                stats,
            )

        return stats


    def collect_source_database_collection_relation_attribute_stats(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        sample_limit: int = 10,
    ):
        source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_property_stats(
            database,
            collection,
            relation,
            attribute,
            sample_limit=sample_limit,
        )

        if stats:
            self.set_source_database_collection_relation_attribute_property(
                source,
                database,
                collection,
                relation,
                attribute,
                "stats",
                stats,
            )

        return stats

    
    def collect_entity_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        source_obj=None,
    ):
        if source_obj is None:
            source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        stats = source_obj.fetch_entity_stats(database, collection, entity)

        if stats:
            self.set_source_database_collection_entity_property(
                source,
                database,
                collection,
                entity,
                "stats",
                stats,
            )

        return stats


    def collect_attribute_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        source_obj=None,
        sample_limit: int = 10,
    ):
        if source_obj is None:
            source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        stats = source_obj.fetch_property_stats(
            database,
            collection,
            entity,
            attribute,
            sample_limit=sample_limit,
        )

        if stats:
            self.set_source_database_collection_entity_attribute_property(
                source,
                database,
                collection,
                entity,
                attribute,
                "stats",
                stats,
            )

        return stats


    def collect_relation_stats(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        source_obj=None,
    ):
        if source_obj is None:
            source_obj = self.connect_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered or connectable: {source}")

        stats = source_obj.fetch_relation_stats(database, collection, relation)

        if stats:
            self.set_source_database_collection_relation_property(
                source,
                database,
                collection,
                relation,
                "stats",
                stats,
            )

        return stats
    
    def get_sources(self):
        return self.list_records(record_type="source", scope="/")


    def get_source_databases(self, source: str):
        return self.list_source_databases(source)


    def get_source_database_collections(self, source: str, database: str):
        return self.list_database_collections(source, database)


    def get_source_database_collection_entities(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.list_collection_entities(source, database, collection)


    def get_source_database_collection_entity_attributes(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        return self.list_entity_attributes(source, database, collection, entity)


    def get_source_database_collection_relations(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.list_collection_relations(source, database, collection)
    
    def get_source_database_properties(self, source: str, database: str):
        return self.get_record_properties(
            database,
            "database",
            f"/source/{source}",
        )


    def get_source_database_collection_properties(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.get_record_properties(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
        )


    def get_source_database_collection_entity_properties(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        return self.get_record_properties(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
        )


    def get_source_database_collection_relation_properties(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        return self.get_record_properties(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
        )
    
    def get_source_description(self, source: str):
        return self.get_record_description(
            source,
            "source",
            "/",
        )


    def set_source_description(self, source: str, description: str):
            return self.set_record_description(
                source,
                "source",
                "/",
                description,
            )
    
    def search_records(
        self,
        input_query: str,
        type: str | None = None,
        scope: str | None = None,
        page: int = 0,
        page_size: int = 5,
        page_limit: int = 10,
        bm25_weight: float | None = None,
        vector_weight: float | None = None,
        value_weight: float | None = None,
        bm25_threshold: float | None = None,
        vector_threshold: float | None = None,
        value_threshold: float | None = None,
        combined_threshold: float | None = None,
        bm25_normalization: str | None = None,
        enable_schema: bool | None = None,
        enable_value_semantics: bool = True,
        hierarchical_enabled: bool | None = None,
        hierarchical_database_types: list | None = None,
        hierarchical_collection_types: list | None = None,
    ):
        overrides = {k: v for k, v in {
            "bm25_weight": bm25_weight,
            "vector_weight": vector_weight,
            "value_weight": value_weight,
            "bm25_threshold": bm25_threshold,
            "vector_threshold": vector_threshold,
            "value_threshold": value_threshold,
            "combined_threshold": combined_threshold,
            "bm25_normalization": bm25_normalization,
            "enable_schema": enable_schema,
            "hierarchical_enabled": hierarchical_enabled,
            "hierarchical_database_types": hierarchical_database_types,
            "hierarchical_collection_types": hierarchical_collection_types,
            "search_limit": page_limit * page_size,
        }.items() if v is not None}

        # database/collection types automatically go hierarchical
        resolved_hierarchical = (
            hierarchical_enabled
            if hierarchical_enabled is not None
            else self.search_engine.hybrid_engine.config.get("hierarchical_enabled", True)
        )
        if resolved_hierarchical and type in ("database", "collection"):
            return self.search_records_hierarchical(
                input_query=input_query,
                type=type,
                scope=scope,
                page=page,
                page_size=page_size,
                page_limit=page_limit,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight,
                value_weight=value_weight,
                bm25_threshold=bm25_threshold,
                vector_threshold=vector_threshold,
                value_threshold=value_threshold,
                combined_threshold=combined_threshold,
                bm25_normalization=bm25_normalization,
                enable_schema=enable_schema,
                enable_value_semantics=enable_value_semantics,
                hierarchical_enabled=hierarchical_enabled,
                hierarchical_database_types=hierarchical_database_types,
                hierarchical_collection_types=hierarchical_collection_types,
            )

        return self.search_engine.hybrid_search(
            query=input_query,
            type=type,
            scope=scope,
            page=page,
            page_size=page_size,
            **overrides,
        )

    def search_records_hierarchical(
        self,
        input_query: str,
        type: str | None = None,
        scope: str | None = None,
        page: int = 0,
        page_size: int = 5,
        page_limit: int = 10,
        bm25_weight: float | None = None,
        vector_weight: float | None = None,
        value_weight: float | None = None,
        bm25_threshold: float | None = None,
        vector_threshold: float | None = None,
        value_threshold: float | None = None,
        combined_threshold: float | None = None,
        bm25_normalization: str | None = None,
        enable_schema: bool | None = None,
        enable_value_semantics: bool = True,
        hierarchical_enabled: bool | None = None,
        hierarchical_database_types: list | None = None,
        hierarchical_collection_types: list | None = None,
    ):
        overrides = {k: v for k, v in {
            "bm25_weight": bm25_weight,
            "vector_weight": vector_weight,
            "value_weight": value_weight,
            "bm25_threshold": bm25_threshold,
            "vector_threshold": vector_threshold,
            "value_threshold": value_threshold,
            "combined_threshold": combined_threshold,
            "bm25_normalization": bm25_normalization,
            "enable_schema": enable_schema,
            "hierarchical_enabled": hierarchical_enabled,
            "hierarchical_database_types": hierarchical_database_types,
            "hierarchical_collection_types": hierarchical_collection_types,
            "search_limit": page_limit * page_size,
        }.items() if v is not None}

        return self.search_engine.search_records_hierarchical(
            query=input_query,
            type=type,
            scope=scope,
            page=page,
            page_size=page_size,
            **overrides,
        )

 

        
