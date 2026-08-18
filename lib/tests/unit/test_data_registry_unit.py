"""Unit tests for DataRegistry hierarchy helpers, connect_source, execute_query,
rebuild flag, and schema generation — all using in-memory backends only."""
import hashlib
import math

import pytest

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource
from blue_data.source.source import DataSource


DIM = 4
HYBRID_CONFIG = {"vector_threshold": 0.0, "combined_threshold": 0.0}


def _emb(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


class StubSource(DataSource):
    def __init__(self, name, databases=None, collections=None, entities=None, relations=None):
        super().__init__(name)
        self._databases = databases or []
        self._collections = collections or ["public"]
        self._entities = entities or {}
        self._relations = relations or {}

    def fetch_databases(self):
        return self._databases

    def fetch_database_collections(self, database):
        return self._collections

    def fetch_database_collection_entities(self, database, collection):
        return self._entities

    def fetch_database_collection_relations(self, database, collection):
        return self._relations


@pytest.fixture
def reg():
    return DataRegistry(store=MemoryJSONSource())


@pytest.fixture
def reg_search():
    return DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource(),
        embedding_fn=_emb,
        vector_dim=DIM,
        rebuild=True,
        hybrid_config=HYBRID_CONFIG,
    )


# ---------- source CRUD ----------

def test_register_and_get_source(reg):
    source = StubSource("mydb")
    reg.register_source(source)
    assert "mydb" in reg.list_sources()
    assert reg.get_source("mydb") is source


def test_deregister_source_removes_live_and_record(reg):
    source = StubSource("mydb")
    reg.register_source(source)
    reg.deregister_source("mydb")
    assert reg.get_source("mydb") is None
    assert reg.get_source_record("mydb") is None


def test_get_sources_returns_source_records(reg):
    reg.register_source(StubSource("s1"))
    reg.register_source(StubSource("s2"))
    sources = reg.get_sources()
    names = {r["name"] for r in sources}
    assert {"s1", "s2"} == names


def test_source_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.set_source_property("mydb", "owner", "team-a")
    assert reg.get_source_property("mydb", "owner") == "team-a"


def test_delete_source_property(reg):
    reg.register_source(StubSource("mydb"))
    reg.set_source_property("mydb", "tmp", "x")
    reg.delete_source_property("mydb", "tmp")
    assert reg.get_source_property("mydb", "tmp") is None


def test_source_connection_helpers(reg):
    reg.register_source(StubSource("mydb"))
    conn = {"protocol": "sqlite", "host": "localhost"}
    reg.set_source_connection("mydb", conn)
    assert reg.get_source_connection("mydb") == conn


def test_source_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.set_source_description("mydb", "Primary data source")
    assert reg.get_source_description("mydb") == "Primary data source"


def test_get_source_properties(reg):
    reg.register_source(StubSource("mydb"))
    reg.set_source_property("mydb", "k", "v")
    props = reg.get_source_properties("mydb")
    assert props["k"] == "v"


# ---------- database CRUD ----------

def test_register_source_database(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    dbs = [r["name"] for r in reg.list_source_databases("mydb")]
    assert "sales" in dbs


def test_deregister_source_database(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.deregister_source_database("mydb", "sales")
    assert reg.get_source_database("mydb", "sales") is None


def test_update_source_database(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.update_source_database("mydb", "sales", description="Sales DB")
    assert reg.get_source_database("mydb", "sales")["description"] == "Sales DB"


def test_database_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.set_source_database_property("mydb", "sales", "region", "us-east")
    assert reg.get_source_database_property("mydb", "sales", "region") == "us-east"


def test_database_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.set_source_database_description("mydb", "sales", "Sales data")
    assert reg.get_source_database_description("mydb", "sales") == "Sales data"


def test_get_source_databases_alias(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    dbs = reg.get_source_databases("mydb")
    assert any(r["name"] == "sales" for r in dbs)


# ---------- collection CRUD ----------

def test_register_source_database_collection(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    colls = [r["name"] for r in reg.list_database_collections("mydb", "sales")]
    assert "public" in colls


def test_deregister_source_database_collection(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.deregister_source_database_collection("mydb", "sales", "public")
    assert reg.get_source_database_collection("mydb", "sales", "public") is None


def test_update_source_database_collection(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.update_source_database_collection("mydb", "sales", "public", description="Public schema")
    assert reg.get_source_database_collection("mydb", "sales", "public")["description"] == "Public schema"


def test_collection_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.set_source_database_collection_property("mydb", "sales", "public", "size", 500)
    assert reg.get_source_database_collection_property("mydb", "sales", "public", "size") == 500


def test_collection_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.set_source_database_collection_description("mydb", "sales", "public", "Public collection")
    assert reg.get_source_database_collection_description("mydb", "sales", "public") == "Public collection"


def test_get_source_database_collections_alias(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    colls = reg.get_source_database_collections("mydb", "sales")
    assert any(r["name"] == "public" for r in colls)


# ---------- entity CRUD ----------

def test_register_source_database_collection_entity(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    entities = [r["name"] for r in reg.list_collection_entities("mydb", "sales", "public")]
    assert "orders" in entities


def test_deregister_source_database_collection_entity(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.deregister_source_database_collection_entity("mydb", "sales", "public", "orders")
    assert reg.get_source_database_collection_entity("mydb", "sales", "public", "orders") is None


def test_update_source_database_collection_entity(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.update_source_database_collection_entity("mydb", "sales", "public", "orders", description="Orders table")
    assert reg.get_source_database_collection_entity("mydb", "sales", "public", "orders")["description"] == "Orders table"


def test_entity_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.set_source_database_collection_entity_property("mydb", "sales", "public", "orders", "pk", "id")
    assert reg.get_source_database_collection_entity_property("mydb", "sales", "public", "orders", "pk") == "id"


def test_entity_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.set_source_database_collection_entity_description("mydb", "sales", "public", "orders", "Order records")
    assert reg.get_source_database_collection_entity_description("mydb", "sales", "public", "orders") == "Order records"


def test_get_entity_properties(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders", properties={"pk": "id"})
    props = reg.get_source_database_collection_entity_properties("mydb", "sales", "public", "orders")
    assert props["pk"] == "id"


# ---------- attribute CRUD ----------

def test_register_entity_attribute(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id")
    attrs = [r["name"] for r in reg.list_entity_attributes("mydb", "sales", "public", "orders")]
    assert "id" in attrs


def test_deregister_entity_attribute(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id")
    reg.deregister_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id")
    assert reg.get_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id") is None


def test_update_entity_attribute(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "total")
    reg.update_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "total", description="Total amount")
    attr = reg.get_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "total")
    assert attr["description"] == "Total amount"


def test_attribute_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id")
    reg.set_source_database_collection_entity_attribute_property("mydb", "sales", "public", "orders", "id", "type", "INTEGER")
    val = reg.get_source_database_collection_entity_attribute_property("mydb", "sales", "public", "orders", "id", "type")
    assert val == "INTEGER"


def test_attribute_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "total")
    reg.set_source_database_collection_entity_attribute_description("mydb", "sales", "public", "orders", "total", "Order total in USD")
    assert reg.get_source_database_collection_entity_attribute_description("mydb", "sales", "public", "orders", "total") == "Order total in USD"


def test_get_entity_attributes_alias(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")
    reg.register_source_database_collection_entity_attribute("mydb", "sales", "public", "orders", "id")
    attrs = reg.get_source_database_collection_entity_attributes("mydb", "sales", "public", "orders")
    assert any(a["name"] == "id" for a in attrs)


# ---------- relation CRUD ----------

def test_register_relation(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    relations = [r["name"] for r in reg.list_collection_relations("mydb", "graph", "default")]
    assert "PLACED" in relations


def test_deregister_relation(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.deregister_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    assert reg.get_source_database_collection_relation("mydb", "graph", "default", "PLACED") is None


def test_update_relation(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.update_source_database_collection_relation("mydb", "graph", "default", "PLACED", description="User placed order")
    assert reg.get_source_database_collection_relation("mydb", "graph", "default", "PLACED")["description"] == "User placed order"


def test_relation_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.set_source_database_collection_relation_property("mydb", "graph", "default", "PLACED", "weight", 1.5)
    assert reg.get_source_database_collection_relation_property("mydb", "graph", "default", "PLACED", "weight") == 1.5


def test_relation_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.set_source_database_collection_relation_description("mydb", "graph", "default", "PLACED", "Placed by user")
    assert reg.get_source_database_collection_relation_description("mydb", "graph", "default", "PLACED") == "Placed by user"


def test_get_collection_relations_alias(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    relations = reg.get_source_database_collection_relations("mydb", "graph", "default")
    assert any(r["name"] == "PLACED" for r in relations)


# ---------- relation attribute CRUD ----------

def test_register_relation_attribute(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.register_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since")
    attrs = reg.get_source_database_collection_relation_attributes("mydb", "graph", "default", "PLACED")
    assert any(a["name"] == "since" for a in attrs)


def test_deregister_relation_attribute(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.register_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since")
    reg.deregister_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since")
    assert reg.get_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since") is None


def test_relation_attribute_property_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.register_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since")
    reg.set_source_database_collection_relation_attribute_property("mydb", "graph", "default", "PLACED", "since", "type", "DATE")
    val = reg.get_source_database_collection_relation_attribute_property("mydb", "graph", "default", "PLACED", "since", "type")
    assert val == "DATE"


def test_relation_attribute_description_helpers(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")
    reg.register_source_database_collection_relation_attribute("mydb", "graph", "default", "PLACED", "since")
    reg.set_source_database_collection_relation_attribute_description("mydb", "graph", "default", "PLACED", "since", "Timestamp")
    assert reg.get_source_database_collection_relation_attribute_description("mydb", "graph", "default", "PLACED", "since") == "Timestamp"


# ---------- connect_source ----------

def test_connect_source_returns_live_if_registered(reg):
    source = StubSource("mydb")
    reg.register_source(source)
    assert reg.connect_source("mydb") is source


def test_connect_source_sqlite_lazy(tmp_path):
    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_record("mydb", "source", "/", properties={
        "_class": "blue_data.source.sql.sqlite.sqlite_sql_source.SQLiteDBSource",
        "connection": {"protocol": "sql/sqlite", "database_directory": str(tmp_path)},
    })
    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
    result = reg.connect_source("mydb")
    assert isinstance(result, SQLiteDBSource)
    assert "mydb" in reg.sources


def test_connect_source_missing_class_raises(reg):
    reg.register_record("mydb", "source", "/", properties={
        "connection": {"protocol": "sql/sqlite"}
    })
    with pytest.raises(ValueError, match="_class"):
        reg.connect_source("mydb")


def test_connect_source_no_properties_returns_none(reg):
    reg.register_record("noprops", "source", "/")
    assert reg.connect_source("noprops") is None


def test_register_source_stores_class_name(reg):
    """register_source should record _class so the source can be reconstructed."""
    source = StubSource("s1")
    reg.register_source(source)
    props = reg.get_source_properties("s1")
    expected = f"{StubSource.__module__}.{StubSource.__qualname__}"
    assert props.get("_class") == expected


def test_connect_source_uses_class_path(tmp_path):
    """connect_source should reconstruct a source via _class without a protocol."""
    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
    reg = DataRegistry(store=MemoryJSONSource())
    source = SQLiteDBSource("s2", properties={"connection": {"database_directory": str(tmp_path)}})
    reg.register_source(source)
    # Evict the live source so connect_source must reconstruct it via _class
    del reg.sources["s2"]
    result = reg.connect_source("s2")
    assert isinstance(result, SQLiteDBSource)
    assert result.name == "s2"


def test_datasource_instantiate_classmethod(tmp_path):
    """DataSource.instantiate should load and return an instance by full class path."""
    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource
    full_path = f"{SQLiteDBSource.__module__}.{SQLiteDBSource.__qualname__}"
    props = {"connection": {"database_directory": str(tmp_path)}}
    result = DataSource.instantiate(full_path, "mydb", properties=props)
    assert isinstance(result, SQLiteDBSource)
    assert result.name == "mydb"


# ---------- execute_query ----------

def test_execute_query_routes_to_source(reg):
    captured = {}

    class RecordingSource(DataSource):
        def __init__(self):
            super().__init__("recorder")

        def execute_query(self, query, database=None, collection=None, optional_properties=None):
            captured["query"] = query
            captured["database"] = database
            return [{"result": "ok"}]

    reg.register_source(RecordingSource())
    result = reg.execute_query("recorder", "SELECT 1", database="db1")
    assert captured["query"] == "SELECT 1"
    assert captured["database"] == "db1"
    assert result == [{"result": "ok"}]


def test_execute_query_raises_for_missing_source(reg):
    with pytest.raises(ValueError, match="not registered"):
        reg.execute_query("ghost", "SELECT 1")


# ---------- get_data_source_schema ----------

def test_get_data_source_schema_dict_format(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "orders")

    schema = reg.get_data_source_schema("mydb", "sales", "public", format="dict")
    assert isinstance(schema, dict)
    assert any(e["name"] == "orders" for e in schema["entities"])


def test_get_data_source_schema_json_format(reg):
    import json
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")

    schema_str = reg.get_data_source_schema("mydb", "sales", "public", format="json")
    parsed = json.loads(schema_str)
    assert "entities" in parsed


def test_get_data_source_schema_includes_relations(reg):
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "graph")
    reg.register_source_database_collection("mydb", "graph", "default")
    reg.register_source_database_collection_relation("mydb", "graph", "default", "PLACED")

    schema = reg.get_data_source_schema("mydb", "graph", "default", format="dict")
    assert any(r["name"] == "PLACED" for r in schema["relations"])


# ---------- rebuild flag (three-state) ----------

def _make_reg_with_mock_engine(instance_rebuild):
    indexed = []
    removed = []

    class MockHybrid:
        config = {}

    class MockSearchEngine:
        hybrid_engine = MockHybrid()

        def index_record(self, record):
            indexed.append(record["name"])

        def remove_record_from_index(self, name, type_, scope):
            removed.append(name)

    reg = DataRegistry(store=MemoryJSONSource(), rebuild=instance_rebuild)
    reg.search_engine = MockSearchEngine()
    return reg, indexed, removed


def test_rebuild_true_forces_index():
    reg, indexed, _ = _make_reg_with_mock_engine(instance_rebuild=False)
    reg.register_record("users", "entity", "/source/mydb", rebuild=True)
    assert "users" in indexed


def test_rebuild_false_suppresses_index():
    reg, indexed, _ = _make_reg_with_mock_engine(instance_rebuild=True)
    reg.register_record("users", "entity", "/source/mydb", rebuild=False)
    assert "users" not in indexed


def test_rebuild_none_defers_to_instance_true():
    reg, indexed, _ = _make_reg_with_mock_engine(instance_rebuild=True)
    reg.register_record("users", "entity", "/source/mydb", rebuild=None)
    assert "users" in indexed


def test_rebuild_none_defers_to_instance_false():
    reg, indexed, _ = _make_reg_with_mock_engine(instance_rebuild=False)
    reg.register_record("users", "entity", "/source/mydb", rebuild=None)
    assert "users" not in indexed


def test_rebuild_true_on_deregister_calls_remove():
    reg, _, removed = _make_reg_with_mock_engine(instance_rebuild=False)
    reg.register_record("users", "entity", "/source/mydb")
    reg.deregister_record("users", "entity", "/source/mydb", rebuild=True)
    assert "users" in removed


# ---------- search routing ----------

def test_search_records_keyword_only_no_vector(reg):
    # Without a vector source, hybrid thresholds may filter results; test via
    # the keyword_search path directly which has no score threshold.
    reg.register_source(StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    results = reg.search_engine.keyword_search("sales")
    # keyword_search returns {"record": {...}, "score": N} dicts
    assert any(r["record"]["name"] == "sales" for r in results)


def test_search_records_type_filter(reg_search):
    reg_search.register_record("orders", "entity", "/source/mydb/database/sales/collection/public")
    reg_search.register_record("sales", "database", "/source/mydb")
    results = reg_search.search_records("orders", type="entity")
    assert all(r["type"] == "entity" for r in results)


def test_search_records_scope_filter(reg_search):
    reg_search.register_record("orders", "entity", "/source/s1/database/db/collection/public")
    reg_search.register_record("events", "entity", "/source/s2/database/db/collection/public")
    results = reg_search.search_records("orders", scope="/source/s1")
    names = [r["name"] for r in results]
    assert "orders" in names
    assert "events" not in names


# ---------- sync_all ----------

def test_sync_all_covers_multiple_sources(tmp_path):
    import sqlite3, os
    for name in ["alpha", "beta"]:
        path = os.path.join(str(tmp_path), f"{name}.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(SQLiteDBSource("src1", properties={"connection": {"database_directory": str(tmp_path)}}))
    reg.register_source(SQLiteDBSource("src2", properties={"connection": {"database_directory": str(tmp_path)}}))

    reg.sync_all(recursive=True)

    for src in ("src1", "src2"):
        dbs = [r["name"] for r in reg.list_source_databases(src)]
        assert "alpha" in dbs
        assert "beta" in dbs


# ---------- execute_query_nl_tools ----------

def _tool_use_response(tool_id, name, input_dict):
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": input_dict}],
    }


def _text_response(text):
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
    }


def make_scripted_llm(*responses):
    queue = list(responses)
    def llm_fn(messages, tools, system=None):
        return queue.pop(0)
    return llm_fn


def test_registry_execute_query_nl_tools_raises_for_missing_source():
    reg = DataRegistry(store=MemoryJSONSource())
    with pytest.raises(ValueError, match="not registered"):
        reg.execute_query_nl_tools("ghost", "how many rows?")


def test_registry_execute_query_nl_tools_no_llm_fn_returns_empty():
    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(StubSource("src"))
    result = reg.execute_query_nl_tools("src", "how many rows?")
    assert result == []


def test_registry_execute_query_nl_tools_exposes_get_enriched_metadata_tool():
    captured_tools = {}

    def llm_fn(messages, tools, system=None):
        captured_tools["names"] = {t["name"] for t in tools}
        return _text_response("done")

    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(StubSource("src"))

    class FakeEnricher:
        pass

    enricher = FakeEnricher()
    enricher._llm_fn = llm_fn
    reg.metadata_enricher = enricher
    reg.execute_query_nl_tools("src", "test query")
    assert "get_enriched_metadata" in captured_tools["names"]


def test_registry_execute_query_nl_tools_get_enriched_metadata_returns_registry_data(tmp_path):
    import sqlite3, os

    db_path = os.path.join(str(tmp_path), "sales.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE orders (id INTEGER, customer TEXT, amount REAL)")
    conn.execute("INSERT INTO orders VALUES (1, 'Alice', 100.0)")
    conn.commit()
    conn.close()

    from blue_data.source.sql.sqlite.sqlite_sql_source import SQLiteDBSource

    reg = DataRegistry(store=MemoryJSONSource())
    src = SQLiteDBSource("sales_src", properties={"connection": {"database_directory": str(tmp_path)}})
    reg.register_source(src)
    reg.sync_source("sales_src", recursive=True)

    # Manually store enriched metadata on the orders entity
    reg.set_record_property(
        "orders", "entity",
        "/source/sales_src/database/sales/collection/public",
        "metadata",
        {"semantic_type": "TRANSACTION", "description": "Customer order records"},
    )

    captured = {}

    def llm_fn(messages, tools, system=None):
        # First turn: call get_enriched_metadata
        if not captured.get("meta_called"):
            captured["meta_called"] = True
            return _tool_use_response("t1", "get_enriched_metadata", {"entity": "orders"})
        # Second turn: inspect what the tool returned and end
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        captured["meta_result"] = block["content"]
        return _text_response("done")

    class FakeEnricher:
        pass

    enricher = FakeEnricher()
    enricher._llm_fn = llm_fn
    reg.metadata_enricher = enricher
    reg.execute_query_nl_tools("sales_src", "describe orders", database="sales", collection="public")

    assert "TRANSACTION" in captured.get("meta_result", "")
