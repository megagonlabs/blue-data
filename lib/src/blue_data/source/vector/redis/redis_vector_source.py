import copy
import json

import numpy as np
import redis

from blue_data.source.vector.vector_source import VectorSource
from blue_data.core.schema import DataSchema


class RedisVectorSource(VectorSource):
    """Redis Vector data source using RedisJSON + RediSearch."""

    def __init__(self, name: str, embedding_fn=None, properties: dict | None = None, **legacy):
        # Deprecation shim: older callers passed host=/port=/db=/password= directly.
        if legacy:
            import warnings
            properties = dict(properties or {})
            connection = dict(properties.get("connection", {}))
            for key in ("host", "port", "db", "password"):
                if key in legacy:
                    connection[key] = legacy.pop(key)
            properties["connection"] = connection
            if legacy:
                raise TypeError(f"RedisVectorSource got unexpected arguments: {sorted(legacy)}")
            warnings.warn(
                "Passing host/port/db/password directly to RedisVectorSource is deprecated; "
                "use properties={'connection': {...}}.",
                DeprecationWarning,
                stacklevel=2,
            )
        super().__init__(name, embedding_fn=embedding_fn, properties=properties)

        # scan_prefix is required: without it upsert/delete build keys as
        # f"{scan_prefix}{collection}:{doc_id}" → literal "None…" keys that no index
        # covers, so writes succeed but every search fails with "No such index". Fail
        # at construction instead. (Validated here, not in _initialize_connection_
        # properties, because the passed connection is merged in only afterwards.) #226
        scan_prefix = self.properties.get("connection", {}).get("scan_prefix")
        if not scan_prefix:
            raise ValueError("RedisVectorSource requires connection.scan_prefix")
        if str(scan_prefix).startswith("PLATFORM"):
            raise ValueError("RedisVectorSource scan_prefix must not use the PLATFORM namespace")

        # RediSearch (FT.CREATE) refuses to create an index on any logical db other than
        # 0 ("Cannot create index on db != 0"). Allowing it meant the index was never
        # built, every KNN failed with "No such index", and registry search silently
        # degraded to BM25-only. Reject it at construction with a clear message instead.
        # Isolate tenants on db 0 with scan_prefix (namespaced since #181), not the db. #215
        db = self.properties.get("connection", {}).get("db", 0)
        try:
            db = int(db)
        except (TypeError, ValueError):
            pass
        if db != 0:
            raise ValueError(
                f"RedisVectorSource requires Redis logical db 0: RediSearch (FT.CREATE) "
                f"cannot create an index on db != 0 (got db={db!r}). Point the vector source "
                f"at db 0 and isolate tenants with connection.scan_prefix."
            )

    def _initialize_connection_properties(self):
        connection = self.properties.get("connection", {})

        connection.setdefault("protocol", "vector/redis")
        connection.setdefault("host", "localhost")
        connection.setdefault("port", 6379)
        connection.setdefault("db", 0)

        self.properties["connection"] = connection

    def _connect(self, **connection):
        config = copy.deepcopy(connection)

        config.pop("protocol", None)
        config.pop("scan_prefix", None)

        # A connection.url authenticates exactly as redis.Redis.from_url does — keeping
        # the username, password, the rediss:// TLS scheme and any query options. #211
        url = config.get("url")
        if url:
            return redis.Redis.from_url(url, decode_responses=False)

        return redis.Redis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            username=config.get("username"),
            password=config.get("password"),
            ssl=config.get("ssl", False),
            decode_responses=False,
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

    def fetch_vector_indices(self):
        return self.connection.execute_command("FT._LIST")

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
            raise Exception("RedisVectorSource requires 'scan_prefix'")

        if not scan_prefix.endswith(":"):
            scan_prefix += ":"

        return [scan_prefix[:-1]]

    def fetch_database_metadata(self, database):
        return {}

    def fetch_database_schema(self, database):
        return {}

    # ---------- collection ----------

    def fetch_database_collections(self, database):
        scan_prefix = self.properties["connection"].get("scan_prefix")

        if not scan_prefix:
            raise Exception("RedisVectorSource requires 'scan_prefix'")

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
                key = self._decode_value(key)

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

    def fetch_database_collection_entities(
        self,
        database,
        collection,
        sample_limit=25,
    ):
        schema = DataSchema()
        return schema.get_entities()

    def fetch_database_collection_relations(self, database, collection):
        return {}

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

    # ---------- helpers ----------

    def _decode_value(self, value):
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value

        if isinstance(value, (list, tuple)):
            return [self._decode_value(item) for item in value]

        if isinstance(value, dict):
            return {
                self._decode_value(key): self._decode_value(val)
                for key, val in value.items()
            }

        return value

    def _namespaced_index(self, index_name):
        """Scope the FT index name by scan_prefix. Index names are global per Redis
        database, so a fixed name (registry_index, a collection name, 'web', ...)
        would be shared by two tenants with different scan_prefix values — the second
        silently reuses the first's index and gets its data. Keys are already
        scan_prefix-scoped; the index name must be too. Idempotent. #181"""
        scan_prefix = self.properties.get("connection", {}).get("scan_prefix") or ""
        if index_name and scan_prefix and not str(index_name).startswith(scan_prefix):
            return f"{scan_prefix}{index_name}"
        return index_name

    def _ft_info(self, index_name):
        raw = self.connection.execute_command("FT.INFO", self._namespaced_index(index_name))

        if isinstance(raw, dict):
            return self._decode_value(raw)

        if not isinstance(raw, (list, tuple)):
            return {"raw": self._decode_value(raw)}

        info = {}
        raw_items = list(raw)

        for index in range(0, len(raw_items), 2):
            key = self._decode_value(raw_items[index])
            value = raw_items[index + 1] if index + 1 < len(raw_items) else None
            info[key] = self._decode_value(value)

        return info

    def _vector_bytes(self, vector):
        if isinstance(vector, (bytes, bytearray)):
            return bytes(vector)

        if isinstance(vector, str):
            raise Exception("Vector must be bytes or a list of floats")

        return np.asarray(vector, dtype=np.float32).tobytes()

    def _build_create_index_command(self, query):
        index_name = query.get("index")
        scan_prefix = self.properties["connection"].get("scan_prefix")
        collection = query.get("collection")
        dimension = query.get("dim")

        if not index_name or not scan_prefix or not collection or dimension is None:
            raise Exception(
                "VECTOR.CREATE_INDEX requires index, scan_prefix, collection, dim"
            )

        prefix = f"{scan_prefix}{collection}:"
        index_name = self._namespaced_index(index_name)

        vector_path = query.get("path", query.get("vector_path", "$.embedding"))
        vector_field = query.get("field", query.get("vector_field", "embedding"))
        algorithm = query.get("algorithm", "HNSW")
        metric = query.get("metric", query.get("distance_metric", "COSINE"))

        # Always index id/node_id/type/name so RETURN projections and the registry's
        # per-record @id:{...} filter work for any caller (#179).
        _standard_fields = [
            ("$.id",      "id",      "TAG"),
            ("$.node_id", "node_id", "TAG"),
            ("$.type",    "type",    "TAG"),
            ("$.name",    "name",    "TAG"),
        ]

        cmd = [
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
        ]

        for path, alias, field_type in _standard_fields:
            cmd.extend([path, "AS", alias, field_type])

        # Caller-supplied extra fields, e.g. node_id for KB sources.
        for extra in (query.get("extra_fields") or []):
            cmd.extend([
                extra["path"],
                "AS",
                extra["name"],
                extra.get("field_type", "TAG"),
            ])

        cmd.extend([
            vector_path, "AS", vector_field,
            "VECTOR", algorithm, "6",
            "TYPE", "FLOAT32",
            "DIM", int(dimension),
            "DISTANCE_METRIC", metric,
        ])

        return cmd

    def _build_knn_command(self, query):
        index_name = query.get("index")
        if not index_name:
            raise Exception("VECTOR.KNN requires index")
        index_name = self._namespaced_index(index_name)

        vector = query.get("vector", query.get("embedding"))

        if vector is None:
            vector = query.get("query_vector", query.get("query_embedding"))

        if vector is None:
            raise Exception("VECTOR.KNN requires query vector")

        index_dimension = query.get("index_dimension")
        if index_dimension is not None and len(vector) != index_dimension:
            raise Exception(
                f"Query vector dimension {len(vector)} does not match "
                f"index dimension {index_dimension}"
            )

        vector = self._vector_bytes(vector)

        k = int(query.get("k", 5))
        vector_field = query.get("field", query.get("vector_field", "embedding"))
        score_alias = query.get("score_alias", query.get("score_field", "score"))
        dialect = int(query.get("dialect", 2))
        filter_expression = query.get("filter", "*")
        return_fields = list(query.get("return_fields", []))
        if not return_fields:
            # Parity with MemoryVectorSource: return the full JSON document by default
            # so rows carry text/url/title/… rather than only {id, score}.
            return_fields = ["$"]

        if score_alias not in return_fields:
            return_fields.append(score_alias)

        search_query = (
            f"{filter_expression}=>[KNN {k} @{vector_field} $vec AS {score_alias}]"
        )

        command = [
            "FT.SEARCH",
            index_name,
            search_query,
            "PARAMS",
            2,
            "vec",
            vector,
            "SORTBY",
            score_alias,
        ]

        if return_fields:
            command.extend(["RETURN", len(return_fields), *return_fields])

        command.extend(["DIALECT", dialect])

        return command

    def _parse_search_results(self, response, score_field="score"):
        # RESP3 returns FT.SEARCH as a mapping ({"results": [...]}); RESP2 returns a
        # flat [total, id, fields, id, fields, ...] list.
        if isinstance(response, dict):
            return self._parse_resp3_results(response, score_field=score_field)
        if not isinstance(response, (list, tuple)) or len(response) == 0:
            return []

        rows = []
        items = list(response)

        for index in range(1, len(items), 2):
            record_id = self._decode_value(items[index])
            raw_fields = items[index + 1] if index + 1 < len(items) else []

            row = {"id": record_id}

            if isinstance(raw_fields, (list, tuple)):
                pairs = list(raw_fields)

                for field_index in range(0, len(pairs), 2):
                    name = self._decode_value(pairs[field_index])
                    value = (
                        pairs[field_index + 1]
                        if field_index + 1 < len(pairs)
                        else None
                    )

                    decoded_value = self._decode_value(value)

                    if name == "$" and isinstance(decoded_value, str):
                        try:
                            row["document"] = json.loads(decoded_value)
                            continue
                        except Exception:
                            pass

                    row[name] = self._coerce_score(decoded_value) if name == score_field else decoded_value

            rows.append(row)

        return rows

    @staticmethod
    def _coerce_score(value):
        """KNN distance must be numeric. Redis returns the score field as a string
        (e.g. '4.99e-05'), while MemoryVectorSource returns a float, so consumers
        that sort on it get lexicographic order. Coerce to float; leave a
        non-numeric value unchanged. #180"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _dget(mapping, key):
        """Fetch *key* from a RESP3 reply mapping, tolerating str or bytes keys."""
        if key in mapping:
            return mapping[key]
        bkey = key.encode() if isinstance(key, str) else key
        return mapping.get(bkey)

    def _parse_resp3_results(self, response, score_field="score"):
        rows = []
        for item in self._dget(response, "results") or []:
            if not isinstance(item, dict):
                continue
            row = {"id": self._decode_value(self._dget(item, "id"))}
            attrs = self._dget(item, "extra_attributes")
            if attrs is None:
                attrs = self._dget(item, "fields")
            if isinstance(attrs, dict):
                for raw_name, raw_value in attrs.items():
                    name = self._decode_value(raw_name)
                    value = self._decode_value(raw_value)
                    if name == "$" and isinstance(value, str):
                        try:
                            row["document"] = json.loads(value)
                            continue
                        except Exception:
                            pass
                    row[name] = self._coerce_score(value) if name == score_field else value
            rows.append(row)
        return rows

    def _existing_index_matches(self, index_name, expected_prefix, dim):
        """Best-effort check that an existing index targets *expected_prefix* with the
        given *dim*, parsed from FT.INFO. Returns ``False`` only on a confirmed
        mismatch; ``True`` when it matches; ``None`` when it can't be determined (so
        create_index stays idempotent instead of raising spuriously). #181"""
        try:
            info = self._ft_info(index_name)
        except Exception:
            return None
        if not isinstance(info, dict):
            return None

        def _to_dict(value):
            if isinstance(value, dict):
                return value
            if isinstance(value, (list, tuple)):
                return {
                    self._decode_value(value[i]): value[i + 1]
                    for i in range(0, len(value) - 1, 2)
                }
            return {}

        prefixes = None
        defn = _to_dict(info.get("index_definition"))
        raw_prefixes = defn.get("prefixes", defn.get("prefix"))
        if raw_prefixes is not None:
            if not isinstance(raw_prefixes, (list, tuple)):
                raw_prefixes = [raw_prefixes]
            prefixes = [self._decode_value(p) for p in raw_prefixes]
            if expected_prefix not in prefixes:
                return False

        dim_found = None
        attrs = info.get("attributes")
        if isinstance(attrs, (list, tuple)):
            for attr in attrs:
                flat = list(attr) if isinstance(attr, (list, tuple)) else None
                if flat is None and isinstance(attr, dict):
                    flat = [x for pair in attr.items() for x in pair]
                if not flat:
                    continue
                decoded = [self._decode_value(x) for x in flat]
                if "dim" in decoded:
                    j = decoded.index("dim")
                    if j + 1 < len(decoded):
                        try:
                            dim_found = int(decoded[j + 1])
                        except (TypeError, ValueError):
                            dim_found = None
        if dim_found is not None and dim is not None and dim_found != dim:
            return False

        if prefixes is None and dim_found is None:
            return None
        return True

    # ---------- primitive operations ----------

    def create_index(
        self,
        index_name: str,
        collection: str,
        dim: int,
        distance_metric: str = "COSINE",
        extra_fields: list | None = None,
    ) -> str:
        conn = self.properties["connection"]
        query = {
            "index": index_name,
            "collection": collection,
            "dim": dim,
            "distance_metric": distance_metric,
            "path": conn.get("vector_path", "$.embedding"),
            "field": conn.get("vector_field", "embedding"),
            "algorithm": conn.get("algorithm", "HNSW"),
            "extra_fields": extra_fields,
        }
        try:
            return self.connection.execute_command(*self._build_create_index_command(query))
        except Exception as e:
            if "already exists" in str(e).lower():
                # Don't blindly reuse: an existing index whose PREFIX or DIM differs
                # would serve another tenant's data (or mismatched vectors). #181
                expected_prefix = f"{conn.get('scan_prefix')}{collection}:"
                if self._existing_index_matches(index_name, expected_prefix, dim) is False:
                    raise Exception(
                        f"RedisVector index '{self._namespaced_index(index_name)}' already "
                        f"exists with a different prefix or dimension (expected prefix "
                        f"'{expected_prefix}', dim {dim}); refusing to reuse it."
                    )
                self.logger.info("RedisVector index '%s' already exists; reusing.", index_name)
                return "OK"
            self.logger.error(f"RedisVector create_index failed: {e}")
            raise

    def upsert(self, collection: str, doc_id: str, doc: dict, embedding_field: str = "embedding") -> str:
        if embedding_field not in doc:
            raise Exception(f"Document must contain embedding field '{embedding_field}'")
        scan_prefix = self.properties["connection"].get("scan_prefix")
        key = f"{scan_prefix}{collection}:{doc_id}"
        try:
            return self.connection.json().set(key, "$", doc)
        except Exception as e:
            self.logger.error(f"RedisVector upsert failed: {e}")
            raise

    def delete(self, collection: str, doc_id: str) -> int:
        scan_prefix = self.properties["connection"].get("scan_prefix")
        key = f"{scan_prefix}{collection}:{doc_id}"
        try:
            return self.connection.delete(key)
        except Exception as e:
            self.logger.error(f"RedisVector delete failed: {e}")
            raise

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
        query = {
            "index": index_name,
            "vector": query_vector,
            "k": k,
            "field": embedding_field,
            "score_alias": score_alias,
            "return_fields": return_fields or [],
            "filter": filter_expr,
        }
        try:
            response = self.connection.execute_command(*self._build_knn_command(query))
            return self._parse_search_results(response, score_field=score_alias)
        except Exception as e:
            self.logger.error(f"RedisVector knn failed: {e}")
            raise