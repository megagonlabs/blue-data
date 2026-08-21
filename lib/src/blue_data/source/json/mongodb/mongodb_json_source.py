import json
import re

from pymongo import MongoClient

from blue_data.source.json.json_source import JSONSource
from blue_data.core.schema import DataSchema


class MongoDBSource(JSONSource):
    """MongoDB data source."""

    def __init__(self, name, properties=None):
        super().__init__(name, properties=properties)
        self._schema_cache = {}

    def _initialize_connection_properties(self):
        connection = self.properties.get("connection", {})
        connection.setdefault("host", "localhost")
        connection.setdefault("port", 27017)
        connection.setdefault("protocol", "json/mongodb")
        self.properties["connection"] = connection

    def _connect(self, **connection):
        protocol = connection.get("protocol", "mongodb")
        host = connection.get("host", "localhost")
        port = connection.get("port", 27017)

        username = connection.get("username") or connection.get("user")
        password = connection.get("password")

        if username and password:
            url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            url = f"{protocol}://{host}:{port}"

        return MongoClient(url)

    def _disconnect(self):
        if getattr(self, "connection", None):
            self.connection.close()
        return None

    def fetch_metadata(self):
        return {}

    def fetch_schema(self):
        return {}

    def fetch_databases(self):
        system_dbs = {"admin", "config", "local"}
        return [
            db
            for db in self.connection.list_database_names()
            if db not in system_dbs
        ]

    def fetch_database_metadata(self, database):
        return {}

    def fetch_database_schema(self, database):
        return {}

    def create_database(self, database, properties=None, overwrite=False):
        if database in self.fetch_databases() and not overwrite:
            return {"status": "skipped"}

        # MongoDB creates databases lazily.
        self.connection[database]["_blue_metadata"].insert_one(
            {"_blue_created": True}
        )
        return {"status": "success"}

    def fetch_database_collections(self, database):
        # Keep Blue's registry convention: collection namespace is "public".
        return ["public"]

    def fetch_database_collection_metadata(self, database, collection):
        return {}

    def create_database_collection(
        self,
        database,
        collection,
        properties=None,
        overwrite=False,
    ):
        return {"status": "registry_only"}

    def fetch_database_collection_entities(
        self,
        database,
        collection,
        sample_limit=10,
    ):
        db = self.connection[database]
        collection_names = db.list_collection_names()

        schema = {}

        for coll_name in collection_names:
            if coll_name == "_blue_metadata":
                continue

            coll = db[coll_name]
            sample_docs = list(coll.find().limit(sample_limit))

            attributes = {}

            for doc in sample_docs:
                for key, value in doc.items():
                    if key not in attributes:
                        attributes[key] = {
                            "type": type(value).__name__,
                            "values": [],
                        }

            schema[coll_name] = {
                "properties": {"sample_count": len(sample_docs)},
                "contents": {"attributes": attributes},
            }

        return schema

    def fetch_database_collection_relations(self, database, collection):
        return {}

    def create_database_collection_entity(
        self,
        database,
        collection,
        entity,
        properties=None,
        overwrite=False,
    ):
        properties = properties or {}
        db = self.connection[database]

        if entity in db.list_collection_names():
            if overwrite:
                db.drop_collection(entity)
            else:
                return {"status": "skipped"}

        db.create_collection(entity)

        sample_document = properties.get("sample_document")
        if sample_document:
            db[entity].insert_one(sample_document)

        return {"status": "success"}

    def create_database_collection_relation(
        self,
        database,
        collection,
        relation,
        properties=None,
        overwrite=False,
    ):
        return {"status": "registry_only"}

    def extract_schema(self, sample, schema=None, source=None):
        if schema is None:
            schema = DataSchema()

        if source is None:
            source = schema.add_entity("ROOT")

        if isinstance(sample, dict):
            for key, value in sample.items():
                if isinstance(value, list):
                    target = schema.add_entity(key)
                    schema.add_relation(source, source + ":" + target, target)
                    if value:
                        self.extract_schema(value[0], schema=schema, source=target)

                elif isinstance(value, dict):
                    target = schema.add_entity(key)
                    schema.add_relation(source, source + ":" + target, target)
                    self.extract_schema(value, schema=schema, source=target)

                else:
                    schema.add_entity_attribute(
                        source,
                        key,
                        {"type": value.__class__.__name__, "values": []},
                    )

        return schema

    # ---------- JSONSource interface ----------

    def get(self, path: str | None = None):
        raise NotImplementedError("MongoDBSource does not implement JSONSource.get")

    def set(self, path: str | None, value) -> None:
        raise NotImplementedError("MongoDBSource does not implement JSONSource.set")

    def delete(self, path: str | None = None) -> None:
        raise NotImplementedError("MongoDBSource does not implement JSONSource.delete")

    def execute_query(
        self,
        query,
        database=None,
        collection=None,
        optional_properties=None,
    ):
        """Execute a compound MongoDB operation.

        query must be a dict with:
            op         – "FIND", "INSERT_ONE", or "DELETE_MANY"
            filter     – query filter document (FIND, DELETE_MANY)
            document   – document to insert (INSERT_ONE)
        """
        if database is None:
            raise Exception("No database provided")

        if collection is None:
            raise Exception("No collection provided")

        if not isinstance(query, dict):
            raise ValueError(
                "MongoDBSource.execute_query expects query as a dict "
                "with 'op' and 'filter' / 'document'"
            )

        db = self.connection[database]
        col = db[collection]

        op = (query.get("op") or "").upper()

        if op == "FIND":
            filter_doc = query.get("filter") or {}
            projection = query.get("projection") or None
            sort = query.get("sort") or None
            limit = int(query.get("limit") or 0)
            cursor = col.find(filter_doc, projection)
            if sort:
                cursor = cursor.sort(list(sort.items()))
            if limit:
                cursor = cursor.limit(limit)
            result = []
            for doc in cursor:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                result.append(doc)
            return result

        if op == "COUNT":
            filter_doc = query.get("filter") or {}
            return [{"count": col.count_documents(filter_doc)}]

        if op == "DISTINCT":
            field = query["field"]
            filter_doc = query.get("filter") or {}
            return [{"values": col.distinct(field, filter_doc)}]

        if op == "AGGREGATE":
            pipeline = query.get("pipeline") or []
            result = []
            for doc in col.aggregate(pipeline):
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                result.append(doc)
            return result

        if op == "INSERT_ONE":
            document = query.get("document") or {}
            res = col.insert_one(document)
            return [{"inserted_id": str(res.inserted_id)}]

        if op == "DELETE_MANY":
            filter_doc = query.get("filter") or {}
            res = col.delete_many(filter_doc)
            return [{"deleted_count": res.deleted_count}]

        raise ValueError(
            f"Unsupported MongoDB operation: {op!r}. "
            "Supported: FIND, COUNT, DISTINCT, AGGREGATE, INSERT_ONE, DELETE_MANY"
        )

    def execute_query_nl(
        self,
        query: str,
        database: str | None = None,
        collection: str | None = None,
        schema: dict | None = None,
        llm_fn=None,
        optional_properties: dict | None = None,
    ) -> list[dict]:
        """Translate *query* from natural language to a MongoDB filter and execute a FIND.

        Requires *llm_fn* — raises ``ValueError`` when absent.
        Calls ``translate_nl_to_native_query`` which asks the LLM to produce a
        JSON filter document (e.g. ``{"status": "active"}``), then wraps it as a
        ``{"op": "FIND", "filter": ...}`` call to ``execute_query``.
        Returns ``[]`` if the LLM response cannot be parsed as valid JSON.
        """
        if llm_fn is None:
            raise ValueError("execute_query_nl requires an llm_fn")
        filter_doc = self.translate_nl_to_native_query(query, schema, llm_fn)
        if filter_doc is None:
            return []
        return self.execute_query(
            {"op": "FIND", "filter": filter_doc},
            database=database,
            collection=collection,
            optional_properties=optional_properties,
        )

    def _format_schema_for_nl(self, schema: dict | None) -> str:
        if not schema:
            return "(no schema available)"
        lines = []
        for entity in schema.get("entities", []):
            name = entity.get("name", "")
            lines.append(f"Collection: {name}")
            for field_name, field_props in entity.get("attributes", {}).items():
                field_type = field_props.get("type", "mixed") if isinstance(field_props, dict) else "mixed"
                lines.append(f"  - {field_name} ({field_type})")
        return "\n".join(lines) or "(no schema available)"

    def _build_nl_prompt(self, query: str, schema_text: str) -> str:
        return (
            "You are a MongoDB expert. Convert the natural language query to a MongoDB filter document (JSON).\n\n"
            f"Collection schema:\n{schema_text}\n\n"
            f"Natural language query: {query}\n\n"
            "Rules:\n"
            "- Return ONLY a valid JSON object representing the filter, no explanation or markdown\n"
            "- Use only fields that exist in the schema above\n"
            "- For 'all documents' or no filter, return {}\n\n"
            "Filter:"
        )

    def _extract_native_query(self, raw: str) -> dict | None:
        raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    # ---------- NL tool loop ----------

    def get_nl_tools(self, database=None, collection=None):
        return [
            {
                "name": "list_collections",
                "description": "List all collections in a MongoDB database.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name"},
                    },
                    "required": ["database"],
                },
            },
            {
                "name": "get_sample",
                "description": "Fetch a small sample of documents from a collection to understand its structure and field values.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string", "description": "MongoDB collection name"},
                        "limit":      {"type": "integer", "description": "Number of sample documents (default 3)"},
                    },
                    "required": ["database", "collection"],
                },
            },
            {
                "name": "get_field_stats",
                "description": "Get statistics for a specific field: distinct value count, sample values, null count, min, max.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string"},
                        "field":      {"type": "string", "description": "Field name"},
                    },
                    "required": ["database", "collection", "field"],
                },
            },
            {
                "name": "find",
                "description": (
                    "Run a MongoDB find query and return matching documents. "
                    "Use filter to select documents, projection to pick fields, "
                    "sort to order results, and limit to cap the result size."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string"},
                        "filter": {
                            "type": "object",
                            "description": "MongoDB filter document (e.g. {\"status\": \"active\"})",
                        },
                        "projection": {
                            "type": "object",
                            "description": "Fields to include (1) or exclude (0)",
                        },
                        "sort": {
                            "type": "object",
                            "description": "Sort specification (e.g. {\"date\": -1} for descending)",
                        },
                        "limit": {"type": "integer", "description": "Max documents to return"},
                    },
                    "required": ["database", "collection"],
                },
            },
            {
                "name": "count",
                "description": "Count documents in a collection matching a filter.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string"},
                        "filter": {
                            "type": "object",
                            "description": "MongoDB filter document",
                        },
                    },
                    "required": ["database", "collection"],
                },
            },
            {
                "name": "aggregate",
                "description": (
                    "Run a MongoDB aggregation pipeline. "
                    "Use for grouping, counting, summing, averaging, and multi-stage transformations."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string"},
                        "pipeline": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": (
                                "Aggregation pipeline stages "
                                "(e.g. [{\"$group\": {\"_id\": \"$status\", \"count\": {\"$sum\": 1}}}])"
                            ),
                        },
                    },
                    "required": ["database", "collection", "pipeline"],
                },
            },
            {
                "name": "distinct",
                "description": "Get all distinct values of a field across a collection.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "database":   {"type": "string"},
                        "collection": {"type": "string"},
                        "field":      {"type": "string", "description": "Field name"},
                        "filter": {
                            "type": "object",
                            "description": "Optional filter to scope the distinct query",
                        },
                    },
                    "required": ["database", "collection", "field"],
                },
            },
        ]

    def execute_nl_tool(self, name, tool_input, database=None, collection=None, optional_properties=None):
        db   = tool_input.get("database", database)
        coll = tool_input.get("collection", collection)

        if name == "list_collections":
            return [
                c for c in self.connection[db].list_collection_names()
                if c != "_blue_metadata"
            ]

        if name == "get_sample":
            return self.execute_query(
                {"op": "FIND", "filter": {}, "limit": int(tool_input.get("limit", 3))},
                database=db, collection=coll,
            )

        if name == "get_field_stats":
            return self.fetch_property_stats(db, "public", coll, tool_input["field"])

        if name == "find":
            q: dict = {"op": "FIND", "filter": tool_input.get("filter") or {}}
            for key in ("projection", "sort", "limit"):
                if key in tool_input:
                    q[key] = tool_input[key]
            return self.execute_query(q, database=db, collection=coll)

        if name == "count":
            return self.execute_query(
                {"op": "COUNT", "filter": tool_input.get("filter") or {}},
                database=db, collection=coll,
            )

        if name == "aggregate":
            return self.execute_query(
                {"op": "AGGREGATE", "pipeline": tool_input["pipeline"]},
                database=db, collection=coll,
            )

        if name == "distinct":
            return self.execute_query(
                {
                    "op": "DISTINCT",
                    "field": tool_input["field"],
                    "filter": tool_input.get("filter") or {},
                },
                database=db, collection=coll,
            )

        raise ValueError(f"Unknown MongoDB tool: {name!r}")

    def _build_nl_tools_system_prompt(self, database=None, collection=None):
        parts = [f"You are a MongoDB expert data assistant for the '{self.name}' data source."]
        if database:
            parts.append(f"The target database is '{database}'.")
        parts += [
            "Use list_collections to discover available collections.",
            "Use get_sample and get_field_stats to understand collection structure and field values.",
            "Use find for filtered document retrieval, count for counting documents, "
            "aggregate for grouping and summarising, and distinct for unique field values.",
            "Always call find, count, or aggregate to produce the final answer.",
        ]
        return " ".join(parts)

    def fetch_source_stats(self):
        stats = {}

        try:
            stats["database_count"] = len(self.fetch_databases())
            stats["server_info"] = self.connection.server_info()

        except Exception as e:
            self.logger.warning(f"Failed to fetch MongoDB source stats: {e}")
            stats["error"] = str(e)

        return stats

    def fetch_database_stats(self, database):
        stats = {}

        try:
            db = self.connection[database]
            command_stats = db.command("dbstats")
            stats["collection_count"] = len(db.list_collection_names())
            stats["size_bytes"] = command_stats.get("dataSize")
            stats["storage_size_bytes"] = command_stats.get("storageSize")

        except Exception as e:
            self.logger.warning(f"Failed to fetch MongoDB database stats: {e}")
            stats["error"] = str(e)

        return stats

    def fetch_collection_stats(
        self,
        database,
        collection,
        entities=None,
        relations=None,
        sample_limit=None,
    ):
        entities = entities or []
        relations = relations or []

        return {
            "num_entities": len(entities),
            "num_relations": len(relations),
        }

    def fetch_entity_stats(self, database, collection, entity):
        stats = {}

        try:
            coll = self.connection[database][entity]
            stats["document_count"] = coll.count_documents({})
            stats["row_count"] = stats["document_count"]

        except Exception as e:
            self.logger.warning(f"Failed to fetch MongoDB entity stats: {e}")
            stats["row_count"] = None
            stats["error"] = str(e)

        return stats

    def fetch_property_stats(
        self,
        database,
        collection,
        entity,
        property_name,
        sample_limit=10,
    ):
        stats = {}

        try:
            coll = self.connection[database][entity]

            non_null_filter = {property_name: {"$exists": True, "$ne": None}}

            stats["count"] = coll.count_documents(non_null_filter)
            stats["null_count"] = coll.count_documents(
                {
                    "$or": [
                        {property_name: {"$exists": False}},
                        {property_name: None},
                    ]
                }
            )

            distinct_values = coll.distinct(property_name, non_null_filter)
            stats["distinct_count"] = len(distinct_values)
            stats["sample_values"] = distinct_values[:sample_limit]

            try:
                values = [
                    v
                    for v in distinct_values
                    if isinstance(v, (int, float, str))
                ]
                stats["min"] = min(values) if values else None
                stats["max"] = max(values) if values else None
            except Exception:
                stats["min"] = None
                stats["max"] = None

            stats["most_common_vals"] = []

        except Exception as e:
            self.logger.warning(
                f"Failed to fetch MongoDB property stats for "
                f"{entity}.{property_name}: {e}"
            )
            return {}

        return stats