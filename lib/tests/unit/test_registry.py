import pytest
from blue_data.registry.registry import Registry


@pytest.fixture
def registry():
    return Registry()


def test_register_and_get_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["name"] == "users"
    assert record["type"] == "entity"


def test_list_records_by_type(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.register_record(name="orders", type="entity", scope="/source/mydb")
    registry.register_record(name="mydb", type="database", scope="/source/mydb")
    entities = registry.list_records(record_type="entity")
    assert len(entities) == 2
    assert all(r["type"] == "entity" for r in entities)


def test_list_records_by_scope(registry):
    registry.register_record(name="users", type="entity", scope="/source/db1")
    registry.register_record(name="orders", type="entity", scope="/source/db2")
    results = registry.list_records(scope="/source/db1")
    assert len(results) == 1
    assert results[0]["name"] == "users"


def test_deregister_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.deregister_record("users", "entity", "/source/mydb")
    assert registry.get_record("users", "entity", "/source/mydb") is None


def _register_source_tree(registry):
    """Register a source -> database -> collection -> entity -> attribute chain."""
    registry.register_record(name="src", type="source", scope="/")
    registry.register_record(name="shop", type="database", scope="/source/src")
    registry.register_record(name="public", type="collection", scope="/source/src/database/shop")
    registry.register_record(
        name="orders", type="entity", scope="/source/src/database/shop/collection/public"
    )
    registry.register_record(
        name="total",
        type="attribute",
        scope="/source/src/database/shop/collection/public/entity/orders",
    )


def test_deregister_record_cascades_to_descendants(registry):
    # design/06 #92: deregistering a source must remove every descendant record.
    _register_source_tree(registry)
    assert len(registry.list_records()) == 5

    registry.deregister_record("src", "source", "/")

    assert registry.list_records() == []


def test_deregister_record_cascade_is_scoped_to_subtree(registry):
    # Deregistering an intermediate node removes only its own subtree.
    _register_source_tree(registry)
    registry.register_record(name="other", type="database", scope="/source/src")

    registry.deregister_record("shop", "database", "/source/src")

    remaining = sorted(f"{r['type']}:{r['name']}" for r in registry.list_records())
    assert remaining == ["database:other", "source:src"]


def test_set_and_get_record_property(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_property("users", "entity", "/source/mydb", "stats", {"row_count": 42})
    value = registry.get_record_property("users", "entity", "/source/mydb", "stats")
    assert value == {"row_count": 42}


def test_update_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", description="old")
    registry.update_record("users", "entity", "/source/mydb", description="new")
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["description"] == "new"


def test_set_and_get_description(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_description("users", "entity", "/source/mydb", "User table")
    desc = registry.get_record_description("users", "entity", "/source/mydb")
    assert desc == "User table"


def test_list_records_recursive_scope(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    registry.register_record(name="public", type="collection", scope="/source/mydb/database/sales")
    registry.register_record(name="orders", type="entity", scope="/source/mydb/database/sales/collection/public")
    results = registry.list_records(scope="/source/mydb", recursive=True)
    names = {r["name"] for r in results}
    assert names == {"sales", "public", "orders"}


def test_list_records_recursive_excludes_sibling_scope(registry):
    registry.register_record(name="db1", type="database", scope="/source/s1")
    registry.register_record(name="db2", type="database", scope="/source/s2")
    results = registry.list_records(scope="/source/s1", recursive=True)
    names = {r["name"] for r in results}
    assert "db1" in names
    assert "db2" not in names


def test_filter_records_by_properties_exact(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", properties={"owner": "alice"})
    registry.register_record(name="orders", type="entity", scope="/source/mydb", properties={"owner": "bob"})
    results = registry.filter_records_by_properties(properties={"owner": "alice"})
    assert len(results) == 1
    assert results[0]["name"] == "users"


def test_filter_records_by_properties_partial_match(registry):
    registry.register_record(name="customer_orders", type="entity", scope="/source/mydb", properties={"desc": "customer purchase orders"})
    registry.register_record(name="products", type="entity", scope="/source/mydb", properties={"desc": "product catalog"})
    results = registry.filter_records_by_properties(properties={"desc": "customer"}, partial_match=True)
    assert len(results) == 1
    assert results[0]["name"] == "customer_orders"


def test_filter_records_by_properties_no_filter_returns_all(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.register_record(name="orders", type="entity", scope="/source/mydb")
    results = registry.filter_records_by_properties()
    assert len(results) == 2


def test_delete_record_property(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_property("users", "entity", "/source/mydb", "owner", "alice")
    registry.delete_record_property("users", "entity", "/source/mydb", "owner")
    assert registry.get_record_property("users", "entity", "/source/mydb", "owner") is None


def test_register_record_json_nested_contents(registry):
    record = {
        "name": "sales",
        "type": "database",
        "scope": "/source/mydb",
        "description": "",
        "properties": {},
        "contents": {
            "collection": {
                "public": {
                    "name": "public",
                    "type": "collection",
                    "scope": "/source/mydb/database/sales",
                    "description": "",
                    "properties": {},
                    "contents": {
                        "entity": {
                            "orders": {
                                "name": "orders",
                                "type": "entity",
                                "scope": "/source/mydb/database/sales/collection/public",
                                "description": "All orders",
                                "properties": {},
                                "contents": {},
                            }
                        }
                    },
                }
            }
        },
    }
    registry.register_record_json(record)
    assert registry.get_record("sales", "database", "/source/mydb") is not None
    assert registry.get_record("public", "collection", "/source/mydb/database/sales") is not None
    orders = registry.get_record("orders", "entity", "/source/mydb/database/sales/collection/public")
    assert orders is not None
    assert orders["description"] == "All orders"


def test_dumps_loads_roundtrip(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", description="Users table")
    registry.register_record(name="orders", type="entity", scope="/source/mydb", description="Orders table")
    serialized = registry.dumps()

    new_reg = Registry()
    new_reg.loads(serialized)
    assert new_reg.get_record("users", "entity", "/source/mydb")["description"] == "Users table"
    assert new_reg.get_record("orders", "entity", "/source/mydb")["description"] == "Orders table"


def test_update_record_merges_properties_deeply(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", properties={"a": 1, "b": {"x": 10}})
    registry.update_record("users", "entity", "/source/mydb", properties={"b": {"y": 20}, "c": 3})
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["properties"]["a"] == 1
    assert record["properties"]["c"] == 3
    assert record["properties"]["b"]["x"] == 10
    assert record["properties"]["b"]["y"] == 20


def test_update_record_creates_if_not_exists(registry):
    registry.update_record("ghost", "entity", "/source/mydb", description="auto-created")
    record = registry.get_record("ghost", "entity", "/source/mydb")
    assert record is not None
    assert record["description"] == "auto-created"


def test_filter_record_contents_all_descendants(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    registry.register_record(name="public", type="collection", scope="/source/mydb/database/sales")
    registry.register_record(name="private", type="collection", scope="/source/mydb/database/sales")
    registry.register_record(name="orders", type="entity", scope="/source/mydb/database/sales/collection/public")

    contents = registry.filter_record_contents("sales", "database", "/source/mydb")
    names = {r["name"] for r in contents}
    assert {"public", "private", "orders"} == names


def test_filter_record_contents_by_type(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    registry.register_record(name="public", type="collection", scope="/source/mydb/database/sales")
    registry.register_record(name="orders", type="entity", scope="/source/mydb/database/sales/collection/public")

    contents = registry.filter_record_contents("sales", "database", "/source/mydb", filter_type="collection")
    assert len(contents) == 1
    assert contents[0]["name"] == "public"


def test_set_get_record_data(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_data("users", "entity", "/source/mydb", key="custom", value={"foo": "bar"})
    val = registry.get_record_data("users", "entity", "/source/mydb", key="custom")
    assert val == {"foo": "bar"}


def test_delete_record_data(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_data("users", "entity", "/source/mydb", key="custom", value={"foo": "bar"})
    registry.delete_record_data("users", "entity", "/source/mydb", key="custom")
    val = registry.get_record_data("users", "entity", "/source/mydb", key="custom")
    assert val is None


def test_get_records_excludes_contents_key(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    records = registry.get_records()
    assert all("contents" not in r for r in records)


def test_deregister_via_record_object(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    record = registry.get_record("users", "entity", "/source/mydb")
    registry.deregister(record)
    assert registry.get_record("users", "entity", "/source/mydb") is None


# ---------------------------------------------------------------------------
# Error cases on missing records
# ---------------------------------------------------------------------------

def test_set_record_property_missing_record_raises(registry):
    with pytest.raises(ValueError, match="Record not found"):
        registry.set_record_property("ghost", "entity", "/source/mydb", "key", "val")


def test_set_record_description_missing_record_raises(registry):
    with pytest.raises(ValueError, match="Record not found"):
        registry.set_record_description("ghost", "entity", "/source/mydb", "desc")


def test_set_record_data_missing_record_raises(registry):
    with pytest.raises(KeyError):
        registry.set_record_data("ghost", "entity", "/source/mydb", key="x", value=1)


def test_delete_record_data_missing_record_raises(registry):
    with pytest.raises(KeyError):
        registry.delete_record_data("ghost", "entity", "/source/mydb", key="x")


# ---------------------------------------------------------------------------
# parse_path
# ---------------------------------------------------------------------------

def test_parse_path_source_only(registry):
    result = registry.parse_path("/source/mydb")
    assert result == {"source": "mydb"}


def test_parse_path_full_hierarchy(registry):
    result = registry.parse_path("/source/mydb/database/sales/collection/public")
    assert result == {"source": "mydb", "database": "sales", "collection": "public"}


def test_parse_path_empty(registry):
    result = registry.parse_path("/")
    assert result == {}


# ---------------------------------------------------------------------------
# _encode / _decode helpers
# ---------------------------------------------------------------------------

def test_encode_dot(registry):
    assert registry._encode("a.b") == "a__DOT__b"


def test_encode_star(registry):
    assert registry._encode("a*b") == "a__STAR__b"


def test_encode_question(registry):
    assert registry._encode("a?b") == "a__Q__b"


def test_decode_roundtrip(registry):
    original = "field.name*with?special"
    assert registry._decode(registry._encode(original)) == original


def test_encode_dict_nested(registry):
    result = registry._encode_dict({"a.b": {"c*d": 1}})
    assert "a__DOT__b" in result
    assert "c__STAR__d" in result["a__DOT__b"]


def test_decode_dict_nested(registry):
    encoded = {"a__DOT__b": {"c__STAR__d": 1}}
    result = registry._decode_dict(encoded)
    assert "a.b" in result
    assert "c*d" in result["a.b"]


def test_encode_list_passthrough(registry):
    result = registry._encode_dict([{"a.b": 1}])
    assert result == [{"a__DOT__b": 1}]


def test_encode_non_string_passthrough(registry):
    assert registry._encode(42) == 42


# ---------------------------------------------------------------------------
# filter_record_contents — filter_name and single
# ---------------------------------------------------------------------------

def test_filter_record_contents_by_name(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    registry.register_record(name="public", type="collection", scope="/source/mydb/database/sales")
    registry.register_record(name="private", type="collection", scope="/source/mydb/database/sales")

    result = registry.filter_record_contents("sales", "database", "/source/mydb", filter_name="public")
    assert len(result) == 1
    assert result[0]["name"] == "public"


def test_filter_record_contents_single_true(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    registry.register_record(name="public", type="collection", scope="/source/mydb/database/sales")

    result = registry.filter_record_contents("sales", "database", "/source/mydb", single=True)
    assert isinstance(result, dict)
    assert result["name"] == "public"


def test_filter_record_contents_single_no_match(registry):
    registry.register_record(name="sales", type="database", scope="/source/mydb")
    result = registry.filter_record_contents("sales", "database", "/source/mydb", single=True)
    assert result is None


# ---------------------------------------------------------------------------
# dump / load (file-based)
# ---------------------------------------------------------------------------

def test_dump_and_load_file(registry, tmp_path):
    registry.register_record(name="users", type="entity", scope="/source/mydb", description="User table")
    out = tmp_path / "export.json"
    registry.dump(str(out))

    new_reg = Registry()
    new_reg.load(str(out))
    record = new_reg.get_record("users", "entity", "/source/mydb")
    assert record is not None
    assert record["description"] == "User table"


# ---------------------------------------------------------------------------
# update_record_json
# ---------------------------------------------------------------------------

def test_update_record_json_updates_description(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb", description="old")
    registry.update_record_json({
        "name": "users",
        "type": "entity",
        "scope": "/source/mydb",
        "description": "new",
    })
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["description"] == "new"


def test_update_record_json_upserts_if_missing(registry):
    registry.update_record_json({
        "name": "ghost",
        "type": "entity",
        "scope": "/source/mydb",
        "description": "auto",
    })
    assert registry.get_record("ghost", "entity", "/source/mydb") is not None


# ---------------------------------------------------------------------------
# register_record_json with recursive=False
# ---------------------------------------------------------------------------

def test_register_record_json_non_recursive_skips_children(registry):
    record = {
        "name": "sales",
        "type": "database",
        "scope": "/source/mydb",
        "description": "",
        "properties": {},
        "contents": {
            "collection": {
                "public": {
                    "name": "public",
                    "type": "collection",
                    "scope": "/source/mydb/database/sales",
                    "description": "",
                    "properties": {},
                    "contents": {},
                }
            }
        },
    }
    registry.register_record_json(record, recursive=False)
    assert registry.get_record("sales", "database", "/source/mydb") is not None
    assert registry.get_record("public", "collection", "/source/mydb/database/sales") is None


# ---------------------------------------------------------------------------
# get_record_data / set_record_data / delete_record_data with key=None
# ---------------------------------------------------------------------------

def test_set_record_data_key_none_sets_data_key(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_data("users", "entity", "/source/mydb", key=None, value={"x": 1})
    record = registry.get_record("users", "entity", "/source/mydb")
    assert record["data"] == {"x": 1}


def test_get_record_data_key_none_returns_full_record(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    record = registry.get_record_data("users", "entity", "/source/mydb", key=None)
    assert record["name"] == "users"


def test_delete_record_data_key_none_removes_data_key(registry):
    registry.register_record(name="users", type="entity", scope="/source/mydb")
    registry.set_record_data("users", "entity", "/source/mydb", key=None, value={"x": 1})
    registry.delete_record_data("users", "entity", "/source/mydb", key=None)
    record = registry.get_record("users", "entity", "/source/mydb")
    assert "data" not in record


# ---------------------------------------------------------------------------
# get_contents
# ---------------------------------------------------------------------------

def test_get_contents_returns_root(registry):
    contents = registry.get_contents()
    assert isinstance(contents, dict)
    assert "contents" in contents


# ---------------------------------------------------------------------------
# filter_records_by_properties — nested dict match
# ---------------------------------------------------------------------------

def test_filter_records_by_nested_properties(registry):
    registry.register_record(
        name="users", type="entity", scope="/source/mydb",
        properties={"metadata": {"owner": "alice", "pii": True}},
    )
    registry.register_record(
        name="orders", type="entity", scope="/source/mydb",
        properties={"metadata": {"owner": "bob", "pii": False}},
    )
    results = registry.filter_records_by_properties(properties={"metadata": {"owner": "alice"}})
    assert len(results) == 1
    assert results[0]["name"] == "users"
