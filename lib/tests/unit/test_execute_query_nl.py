"""Unit tests for execute_query_nl across DataSource, SQLSource, Neo4jGraphSource, MongoDBSource, and DataRegistry."""
import pytest

from blue_data.source.source import DataSource
from blue_data.source.sql.sql_source import SQLSource
from blue_data.source.graph.neo4j.neo4j_graph_source import NEO4JSource
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


# ---------- Neo4jGraphSource ----------

class StubNeo4jSource(NEO4JSource):
    """Neo4jGraphSource with all IO bypassed — never touches a real Neo4j instance."""

    def __init__(self):
        self.name = "neo4jstub"
        self.properties = {}
        self.logger = __import__("logging").getLogger(self.__class__.__name__)
        self._schema_cache = {}
        self.last_query = None

    # GraphSource abstract methods
    def add_node(self, database, label, properties=None, node_id=None): return ""
    def get_node(self, database, node_id): return None
    def delete_node(self, database, node_id): pass
    def update_node(self, database, node_id, properties): pass
    def match_nodes(self, database, label=None, properties=None): return []
    def add_edge(self, database, source_id, edge_type, target_id, properties=None): return ""
    def delete_edge(self, database, source_id, edge_type, target_id): pass
    def update_edge(self, database, source_id, edge_type, target_id, properties): pass
    def match_edges(self, database, edge_type=None, source_id=None, target_id=None, properties=None): return []
    def get_neighbors(self, database, node_id, edge_type=None, direction="both"): return []

    def execute_query(self, query, database=None, collection=None, optional_properties=None):
        self.last_query = query
        return [{"n": "result"}]


class TestNeo4jSourceNL:
    def test_raises_without_llm_fn(self):
        src = StubNeo4jSource()
        with pytest.raises(ValueError, match="llm_fn"):
            src.execute_query_nl("find all users", database="neo4j")

    def test_translates_and_executes(self):
        src = StubNeo4jSource()
        result = src.execute_query_nl(
            "find all users",
            database="neo4j",
            llm_fn=lambda p: "MATCH (n:User) RETURN n",
        )
        assert result == [{"n": "result"}]
        assert src.last_query is not None
        assert "MATCH" in src.last_query.upper()

    def test_strips_markdown_code_block(self):
        src = StubNeo4jSource()
        src.execute_query_nl(
            "find users",
            database="neo4j",
            llm_fn=lambda p: "```cypher\nMATCH (n:User) RETURN n\n```",
        )
        assert "```" not in src.last_query

    def test_returns_empty_when_llm_returns_empty(self):
        src = StubNeo4jSource()
        result = src.execute_query_nl(
            "find users",
            database="neo4j",
            llm_fn=lambda p: "",
        )
        assert result == []

    def test_format_schema_for_nl_entities_only(self):
        src = StubNeo4jSource()
        schema = {
            "entities": [
                {"name": "User", "attributes": {"name": {"type": "STRING"}, "age": {"type": "INTEGER"}}},
                {"name": "Post", "attributes": {}},
            ],
            "relations": [],
        }
        text = src._format_schema_for_nl(schema)
        assert "Node labels:" in text
        assert "User" in text
        assert "name (STRING)" in text
        assert "Post" in text

    def test_format_schema_for_nl_with_relations(self):
        src = StubNeo4jSource()
        schema = {
            "entities": [
                {"name": "User", "attributes": {}},
                {"name": "Post", "attributes": {}},
            ],
            "relations": [
                {"name": "WROTE", "source": "User", "target": "Post", "properties": {}},
            ],
        }
        text = src._format_schema_for_nl(schema)
        assert "Relationship types:" in text
        assert "(User)-[:WROTE]->(Post)" in text

    def test_format_schema_for_nl_relation_with_props(self):
        src = StubNeo4jSource()
        schema = {
            "entities": [],
            "relations": [
                {"name": "KNOWS", "source": "Person", "target": "Person", "properties": {"since": {"type": "DATE"}}},
            ],
        }
        text = src._format_schema_for_nl(schema)
        assert "since (DATE)" in text

    def test_format_schema_for_nl_empty(self):
        src = StubNeo4jSource()
        assert "no schema" in src._format_schema_for_nl(None)

    def test_extract_native_query_match(self):
        src = StubNeo4jSource()
        raw = "MATCH (n:User) RETURN n"
        assert src._extract_native_query(raw) == raw

    def test_extract_native_query_strips_markdown(self):
        src = StubNeo4jSource()
        raw = "```cypher\nMATCH (n:User) RETURN n\n```"
        result = src._extract_native_query(raw)
        assert result == "MATCH (n:User) RETURN n"

    def test_extract_native_query_call(self):
        src = StubNeo4jSource()
        raw = "CALL db.labels()"
        assert src._extract_native_query(raw).startswith("CALL")

    def test_build_nl_prompt_contains_dialect_and_query(self):
        src = StubNeo4jSource()
        prompt = src._build_nl_prompt("find all users", "Node labels:\n  User")
        assert "Cypher" in prompt
        assert "find all users" in prompt
        assert "Node labels:" in prompt


# ---------- _build_nl_prompt ----------

class TestBuildNlPrompt:
    def test_sql_prompt_contains_dialect_and_query(self):
        src = StubSQLSource()
        prompt = src._build_nl_prompt("list all orders", "Table: orders\n  - id (INTEGER)")
        assert "SQL" in prompt
        assert "list all orders" in prompt
        assert "Table: orders" in prompt

    def test_mongo_prompt_contains_dialect_and_query(self):
        src = StubMongoDBSource()
        prompt = src._build_nl_prompt("find active users", "Collection: users\n  - status (string)")
        assert "MongoDB" in prompt
        assert "find active users" in prompt
        assert "Collection: users" in prompt


# ---------- translate_nl_to_native_query ----------

class TestTranslateNlToNativeQuery:
    def test_returns_none_when_llm_returns_empty_string(self):
        src = StubSQLSource()
        result = src.translate_nl_to_native_query("query", None, lambda p: "")
        assert result is None

    def test_calls_hooks_in_order(self):
        """Verify format_schema → build_prompt → llm_fn → extract chain."""
        src = StubSQLSource()
        calls = []

        original_format = src._format_schema_for_nl
        original_build = src._build_nl_prompt
        original_extract = src._extract_native_query

        src._format_schema_for_nl = lambda s: (calls.append("format"), original_format(s))[1]
        src._build_nl_prompt = lambda q, st: (calls.append("build"), original_build(q, st))[1]
        src._extract_native_query = lambda r: (calls.append("extract"), original_extract(r))[1]

        src.translate_nl_to_native_query("q", None, lambda p: "SELECT 1")
        assert calls == ["format", "build", "extract"]

    def test_passes_schema_text_into_prompt(self):
        src = StubSQLSource()
        received_prompt = {}

        def llm_fn(prompt):
            received_prompt["value"] = prompt
            return "SELECT 1"

        schema = {"entities": [{"name": "orders", "attributes": {}}], "relations": []}
        src.translate_nl_to_native_query("get orders", schema, llm_fn)
        assert "Table: orders" in received_prompt["value"]


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
