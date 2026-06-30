"""Unit tests for execute_query_nl across DataSource, SQLSource, NEO4JSource, MongoDBSource, and DataRegistry."""
import pytest

from blue_data.source.source import DataSource
from blue_data.source.sql.sql_source import SQLSource
from blue_data.source.json.mongodb.mongodb_json_source import MongoDBSource
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource


# ---------- helpers ----------

def _llm_fn(prompt: str) -> str:
    """Stub LLM that echoes back a fixed SQL or Cypher depending on prompt content."""
    if "Cypher" in prompt:
        return "MATCH (n) RETURN n LIMIT 10"
    return "SELECT * FROM orders LIMIT 10"


def _llm_fn_with_markdown(prompt: str) -> str:
    return "```sql\nSELECT id FROM orders\n```"


# ---------- DataSource base ----------

class TestDataSourceBase:
    def test_execute_query_nl_returns_empty_list(self):
        src = DataSource("test")
        result = src.execute_query_nl("show me all orders")
        assert result == []

    def test_execute_query_nl_ignores_llm_fn(self):
        src = DataSource("test")
        result = src.execute_query_nl("query", llm_fn=_llm_fn)
        assert result == []


# ---------- SQLSource ----------

class StubSQLSource(SQLSource):
    """Minimal SQLSource that records the last query executed."""

    def __init__(self):
        super().__init__("stub")
        self.last_query = None

    def _db_connect(self, database):
        raise NotImplementedError("not used in unit tests")

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        self.last_query = query
        return [{"result": "ok"}]


class TestSQLSourceNL:
    def test_raises_without_llm_fn(self):
        src = StubSQLSource()
        with pytest.raises(ValueError, match="llm_fn"):
            src.execute_query_nl("show me all orders", database="mydb")

    def test_translates_and_executes(self):
        src = StubSQLSource()
        result = src.execute_query_nl(
            "show me all orders",
            database="mydb",
            llm_fn=_llm_fn,
        )
        assert result == [{"result": "ok"}]
        assert "SELECT" in src.last_query.upper()

    def test_strips_markdown_code_block(self):
        src = StubSQLSource()
        src.execute_query_nl("get ids", database="mydb", llm_fn=_llm_fn_with_markdown)
        assert src.last_query is not None
        assert "```" not in src.last_query

    def test_format_schema_for_nl_empty(self):
        src = StubSQLSource()
        text = src._format_schema_for_nl(None)
        assert "no schema" in text

    def test_format_schema_for_nl_with_entities(self):
        src = StubSQLSource()
        schema = {
            "entities": [
                {
                    "name": "orders",
                    "attributes": {
                        "id": {"type": "INTEGER"},
                        "total": {"type": "REAL"},
                    },
                }
            ],
            "relations": [],
        }
        text = src._format_schema_for_nl(schema)
        assert "Table: orders" in text
        assert "id (INTEGER)" in text
        assert "total (REAL)" in text

    def test_extract_native_query_strips_markdown(self):
        src = StubSQLSource()
        raw = "```sql\nSELECT * FROM foo\n```"
        result = src._extract_native_query(raw)
        assert result == "SELECT * FROM foo"

    def test_extract_native_query_plain(self):
        src = StubSQLSource()
        raw = "SELECT id, name FROM customers WHERE active = 1"
        assert src._extract_native_query(raw) == raw


# ---------- MongoDBSource ----------

class StubMongoDBSource(MongoDBSource):
    """MongoDBSource with mocked connection — never touches a real MongoDB."""

    def __init__(self):
        # Bypass __init__ to avoid real connection
        self.name = "mongostub"
        self.properties = {}
        self.logger = __import__("logging").getLogger(self.__class__.__name__)
        self._schema_cache = {}
        self.last_query = None

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        self.last_query = query
        return [{"_id": "abc", "name": "test"}]


class TestMongoDBSourceNL:
    def test_raises_without_llm_fn(self):
        src = StubMongoDBSource()
        with pytest.raises(ValueError, match="llm_fn"):
            src.execute_query_nl("find active users", database="mydb", collection="users")

    def test_translates_and_executes_find(self):
        src = StubMongoDBSource()

        def llm_fn(prompt):
            return '{"status": "active"}'

        result = src.execute_query_nl(
            "find active users",
            database="mydb",
            collection="users",
            llm_fn=llm_fn,
        )
        assert result == [{"_id": "abc", "name": "test"}]
        assert src.last_query == {"op": "FIND", "filter": {"status": "active"}}

    def test_strips_markdown_code_block(self):
        src = StubMongoDBSource()

        def llm_fn(prompt):
            return "```json\n{\"active\": true}\n```"

        src.execute_query_nl("find active", database="mydb", collection="users", llm_fn=llm_fn)
        assert src.last_query["filter"] == {"active": True}

    def test_all_documents_empty_filter(self):
        src = StubMongoDBSource()

        def llm_fn(prompt):
            return "{}"

        src.execute_query_nl("get all users", database="mydb", collection="users", llm_fn=llm_fn)
        assert src.last_query["filter"] == {}

    def test_returns_empty_on_invalid_json(self):
        src = StubMongoDBSource()

        def llm_fn(prompt):
            return "not valid json at all"

        result = src.execute_query_nl("something", database="mydb", collection="users", llm_fn=llm_fn)
        assert result == []

    def test_format_schema_for_nl_empty(self):
        src = StubMongoDBSource()
        text = src._format_schema_for_nl(None)
        assert "no schema" in text

    def test_format_schema_for_nl_with_entities(self):
        src = StubMongoDBSource()
        schema = {
            "entities": [
                {
                    "name": "users",
                    "attributes": {
                        "name": {"type": "string"},
                        "age": {"type": "int"},
                    },
                }
            ]
        }
        text = src._format_schema_for_nl(schema)
        assert "Collection: users" in text
        assert "name (string)" in text
        assert "age (int)" in text

    def test_extract_native_query_plain(self):
        src = StubMongoDBSource()
        raw = '{"status": "active", "age": {"$gt": 18}}'
        result = src._extract_native_query(raw)
        assert result == {"status": "active", "age": {"$gt": 18}}

    def test_extract_native_query_with_preamble(self):
        src = StubMongoDBSource()
        raw = 'Here is the filter: {"name": "Alice"}'
        result = src._extract_native_query(raw)
        assert result == {"name": "Alice"}


# ---------- DataRegistry ----------

class StubNLSource(DataSource):
    """DataSource that records the last execute_query_nl call."""

    def __init__(self):
        super().__init__("nlsrc", properties={"connection": {"protocol": "stub"}})
        self.calls = []

    def execute_query_nl(self, query, database=None, collection=None, schema=None, llm_fn=None, optional_properties=None):
        self.calls.append({
            "query": query,
            "database": database,
            "collection": collection,
            "schema": schema,
            "llm_fn": llm_fn,
        })
        return [{"row": 1}]

    def fetch_databases(self):
        return ["mydb"]

    def fetch_database_collections(self, database):
        return ["public"]


class FakeEnricher:
    def __init__(self, llm_fn):
        self._llm_fn = llm_fn


@pytest.fixture
def reg_with_source():
    reg = DataRegistry(store=MemoryJSONSource())
    src = StubNLSource()
    reg.register_source(src)
    return reg, src


class TestDataRegistryNL:
    def test_raises_for_unknown_source(self, reg_with_source):
        reg, _ = reg_with_source
        with pytest.raises(ValueError, match="not registered"):
            reg.execute_query_nl("unknown_src", "show me everything")

    def test_passes_llm_fn_from_enricher(self, reg_with_source):
        reg, src = reg_with_source
        reg.metadata_enricher = FakeEnricher(_llm_fn)
        reg.execute_query_nl("nlsrc", "show me all orders", database="mydb", collection="public")
        assert len(src.calls) == 1
        assert src.calls[0]["llm_fn"] is _llm_fn

    def test_llm_fn_is_none_when_no_enricher(self, reg_with_source):
        reg, src = reg_with_source
        reg.metadata_enricher = None
        reg.execute_query_nl("nlsrc", "show me all orders", database="mydb", collection="public")
        assert src.calls[0]["llm_fn"] is None

    def test_schema_built_from_registry(self, reg_with_source):
        reg, src = reg_with_source
        reg.register_source_database(src.name, "mydb")
        reg.register_source_database_collection(src.name, "mydb", "public")
        reg.register_source_database_collection_entity(src.name, "mydb", "public", "orders")
        reg.register_source_database_collection_entity_attribute(
            src.name, "mydb", "public", "orders", "id",
            properties={"info": {"type": "INTEGER"}, "description": None},
        )
        reg.register_source_database_collection_entity_attribute(
            src.name, "mydb", "public", "orders", "total",
            properties={"info": {"type": "REAL"}, "description": None},
        )

        reg.execute_query_nl("nlsrc", "get orders", database="mydb", collection="public")
        schema = src.calls[0]["schema"]
        assert schema is not None
        assert len(schema["entities"]) == 1
        entity = schema["entities"][0]
        assert entity["name"] == "orders"
        assert entity["attributes"]["id"]["type"] == "INTEGER"
        assert entity["attributes"]["total"]["type"] == "REAL"

    def test_schema_is_none_when_no_database_collection(self, reg_with_source):
        reg, src = reg_with_source
        reg.execute_query_nl("nlsrc", "show me everything")
        assert src.calls[0]["schema"] is None

    def test_returns_source_results(self, reg_with_source):
        reg, src = reg_with_source
        result = reg.execute_query_nl("nlsrc", "show me all orders")
        assert result == [{"row": 1}]
