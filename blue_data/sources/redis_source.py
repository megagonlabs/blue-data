import copy
import logging

import redis

from blue_data.core.source import DataSource
from blue_data.core.schema import DataSchema


class RedisSource(DataSource):
    """RedisJSON data source."""

    def __init__(self, name: str, properties: dict | None = None):
        super().__init__(name, properties=properties)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialize_connection_properties()
        self.connection = self._connect(**self.properties["connection"])

    def _initialize_connection_properties(self):
        connection = self.properties.get("connection", {})

        connection.setdefault("host", "localhost")
        connection.setdefault("port", 6379)
        connection.setdefault("protocol", "redis")
        connection.setdefault("subprotocol", "json")
        connection.setdefault("db", 0)

        scan_prefix = connection.get("scan_prefix")
        if not scan_prefix:
            raise Exception("RedisSource requires 'scan_prefix'")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        connection["scan_prefix"] = scan_prefix
        self.properties["connection"] = connection

    def _connect(self, **connection):
        config = copy.deepcopy(connection)

        config.pop("protocol", None)
        config.pop("subprotocol", None)
        config.pop("scan_prefix", None)

        return redis.Redis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=config.get("password"),
            decode_responses=True,
        )

    def _disconnect(self):
        try:
            self.connection.close()
        except Exception:
            pass
        return None

    # ---------- source ----------

    def fetch_metadata(self):
        return {}

    def fetch_schema(self):
        return {}

    def fetch_source_stats(self):
        stats = {}

        try:
            info = self.connection.info()
            stats["redis_version"] = info.get("redis_version")
            stats["connected_clients"] = info.get("connected_clients")
            stats["used_memory"] = info.get("used_memory_human")
            stats["total_keys"] = self.connection.dbsize()

        except Exception as e:
            self.logger.warning(f"Failed to fetch Redis source stats: {e}")
            stats["error"] = str(e)

        return stats

    # ---------- database ----------

    def fetch_databases(self):
        scan_prefix = self.properties["connection"].get("scan_prefix")

        if not scan_prefix:
            raise Exception("RedisSource requires 'scan_prefix'")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        return [scan_prefix[:-1]]

    def fetch_database_metadata(self, database):
        return {}

    def fetch_database_schema(self, database):
        return {}

    def create_database(self, database, properties=None, overwrite=False):
        return {"status": "registry_only"}

    def fetch_database_stats(self, database):
        return self.fetch_source_stats()

    # ---------- collection ----------

    def fetch_database_collections(self, database):
        scan_prefix = self.properties["connection"].get("scan_prefix")

        if not scan_prefix:
            raise Exception("RedisSource requires 'scan_prefix'")

        if scan_prefix.startswith("PLATFORM"):
            raise Exception("Invalid scan_prefix: cannot use PLATFORM namespace")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        pattern = f"{scan_prefix}*"
        prefix_len = len(scan_prefix)

        cursor = 0
        collections = set()

        while True:
            cursor, keys = self.connection.scan(
                cursor=cursor,
                match=pattern,
                count=500,
            )

            for key in keys:
                if not isinstance(key, str):
                    continue

                if not key.startswith(scan_prefix):
                    continue

                remainder = key[prefix_len:]
                if not remainder:
                    continue

                collection_name = remainder.split(":")[0]
                if collection_name:
                    collections.add(collection_name)

            if cursor == 0:
                break

        return list(collections)

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

    def fetch_collection_stats(
        self,
        database,
        collection,
        entities=None,
        relations=None,
        sample_limit=None,
    ):
        return {
            "num_entities": len(entities or []),
            "num_relations": len(relations or []),
        }

    # ---------- entities / relations ----------

    def _extract_schema_from_sample(self, sample, schema, source):
        if not isinstance(sample, dict):
            return

        for key, value in sample.items():
            if isinstance(value, list):
                target = schema.add_entity(key)
                schema.add_relation(source, f"{source}:{target}", target)

                if value and isinstance(value[0], dict):
                    self._extract_schema_from_sample(
                        sample=value[0],
                        schema=schema,
                        source=target,
                    )

            elif isinstance(value, dict):
                target = schema.add_entity(key)
                schema.add_relation(source, f"{source}:{target}", target)

                self._extract_schema_from_sample(
                    sample=value,
                    schema=schema,
                    source=target,
                )

            else:
                schema.add_entity_property(
                    source,
                    key,
                    {
                        "type": value.__class__.__name__,
                        "values": [],
                    },
                )

    def fetch_database_collection_entities(
        self,
        database,
        collection,
        sample_limit=25,
    ):
        schema = DataSchema()
        root_entity = schema.add_entity(collection)

        scan_prefix = self.properties["connection"].get("scan_prefix")

        if not scan_prefix:
            raise Exception("RedisSource requires 'scan_prefix'")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        pattern = f"{scan_prefix}{collection}:*"

        cursor = 0
        samples = []

        while True:
            cursor, keys = self.connection.scan(
                cursor=cursor,
                match=pattern,
                count=500,
            )

            for key in keys:
                try:
                    doc = self.connection.json().get(key)
                except Exception:
                    continue

                if isinstance(doc, dict):
                    samples.append(doc)

                if len(samples) >= sample_limit:
                    break

            if cursor == 0 or len(samples) >= sample_limit:
                break

        for doc in samples:
            self._extract_schema_from_sample(doc, schema, root_entity)

        return schema.get_entities()

    def fetch_database_collection_relations(self, database, collection):
        schema = DataSchema()
        root_entity = schema.add_entity(collection)

        scan_prefix = self.properties["connection"].get("scan_prefix")

        if not scan_prefix:
            return {}

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        pattern = f"{scan_prefix}{collection}:*"

        cursor = 0
        samples = []

        while True:
            cursor, keys = self.connection.scan(
                cursor=cursor,
                match=pattern,
                count=500,
            )

            for key in keys:
                try:
                    doc = self.connection.json().get(key)
                except Exception:
                    continue

                if isinstance(doc, dict):
                    samples.append(doc)

                if len(samples) >= 25:
                    break

            if cursor == 0 or len(samples) >= 25:
                break

        for doc in samples:
            self._extract_schema_from_sample(doc, schema, root_entity)

        return schema.get_relations()

    def create_database_collection_entity(
        self,
        database,
        collection,
        entity,
        properties=None,
        overwrite=False,
    ):
        return {"status": "registry_only"}

    def create_database_collection_relation(
        self,
        database,
        collection,
        relation,
        properties=None,
        overwrite=False,
    ):
        return {"status": "registry_only"}

    def fetch_entity_stats(self, database, collection, entity):
        return {}

    def fetch_property_stats(
        self,
        database,
        collection,
        entity,
        property_name,
        sample_limit=10,
    ):
        return {}

    # ---------- query ----------

    def execute_query(
        self,
        query,
        database=None,
        collection=None,
        optional_properties=None,
    ):
        optional_properties = optional_properties or {}

        if not isinstance(query, dict):
            raise Exception("RedisSource expects query as a dict")

        op = query.get("op")
        if not op:
            raise Exception("Redis query must include 'op'")

        op = op.upper()
        path = query.get("path", "$")

        if database is None:
            raise Exception("RedisSource requires database")

        if collection is None:
            raise Exception("RedisSource requires collection")

        doc_id = query.get("id")
        if doc_id is None:
            raise Exception("RedisSource requires id in query")

        scan_prefix = self.properties["connection"].get("scan_prefix")
        if not scan_prefix:
            raise Exception("RedisSource requires scan_prefix")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        key = f"{scan_prefix}{collection}:{doc_id}"

        try:
            if op == "JSON.GET":
                result = self.connection.json().get(key, path)

                if isinstance(result, list) and len(result) == 1:
                    return result[0]

                return result

            if op == "JSON.SET":
                value = query.get("value")
                if value is None:
                    raise Exception("JSON.SET requires value")

                return self.connection.json().set(key, path, value)

            if op == "JSON.DEL":
                return self.connection.json().delete(key, path)

            raise Exception(f"Unsupported Redis operation: {op}")

        except Exception as e:
            self.logger.error(f"Redis query failed: {e}")
            raise