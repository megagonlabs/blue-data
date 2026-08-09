"""Integration tests for MySQLDBSource.

Requires a running MySQL instance. Auto-skipped when unavailable.

Default connection: localhost:3306, user=root, password="", database=mysql.
Override via: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD.

Each test that mutates data creates a uniquely named database and drops
it on teardown.

Run just these tests:
    python3 -m pytest lib/tests/integration/test_mysql_source.py -v
"""
import os
import uuid

import pytest

try:
    import mysql.connector as _mc
except ImportError:
    _mc = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _mysql_conn_kwargs():
    return {
        "host":     os.environ.get("MYSQL_HOST",     "localhost"),
        "port":     int(os.environ.get("MYSQL_PORT",  "3306")),
        "user":     os.environ.get("MYSQL_USER",     "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": "mysql",
    }


def _mysql_available():
    if _mc is None:
        return False
    try:
        conn = _mc.connect(**_mysql_conn_kwargs())
        conn.close()
        return True
    except Exception:
        return False


skip_no_mysql = pytest.mark.skipif(
    not _mysql_available(),
    reason="MySQL not available — set MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD or start a local server",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def src():
    from blue_data.source.sql.mysql.mysql_sql_source import MySQLDBSource
    kwargs = _mysql_conn_kwargs()
    source = MySQLDBSource(
        name="test_mysql",
        properties={"connection": {
            "host":     kwargs["host"],
            "port":     kwargs["port"],
            "user":     kwargs["user"],
            "password": kwargs["password"],
            "database": kwargs["database"],
        }},
    )
    yield source
    source._disconnect()


@pytest.fixture
def testdb(src):
    """Create a uniquely named test database and drop it on teardown."""
    db_name = f"bd_test_{uuid.uuid4().hex[:12]}"
    src.create_database(db_name, overwrite=True)
    yield db_name
    conn = src._db_connect(db_name)
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
    conn.commit()
    cur.close()
    src._db_disconnect(conn)


# ---------------------------------------------------------------------------
# Source-level
# ---------------------------------------------------------------------------

@skip_no_mysql
def test_fetch_source_stats(src):
    stats = src.fetch_source_stats()
    assert "version" in stats
    assert stats["version"]  # non-empty string


@skip_no_mysql
def test_fetch_databases_excludes_system_dbs(src):
    dbs = src.fetch_databases()
    system = {"information_schema", "performance_schema", "sys", "mysql"}
    assert not (system & set(dbs)), "system databases should be excluded"


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

@skip_no_mysql
def test_create_database(src, testdb):
    assert testdb in src.fetch_databases()


@skip_no_mysql
def test_create_database_skips_when_exists(src, testdb):
    result = src.create_database(testdb, overwrite=False)
    assert result["status"] == "skipped"


@skip_no_mysql
def test_create_database_overwrite(src, testdb):
    result = src.create_database(testdb, overwrite=True)
    assert result["status"] == "success"
    assert testdb in src.fetch_databases()


@skip_no_mysql
def test_fetch_database_stats(src, testdb):
    stats = src.fetch_database_stats(testdb)
    assert "size_bytes" in stats
    assert "table_count" in stats
    assert stats["table_count"] == 0


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@skip_no_mysql
def test_fetch_database_collections_always_public(src, testdb):
    assert src.fetch_database_collections(testdb) == ["public"]


@skip_no_mysql
def test_create_database_collection_returns_registry_only(src, testdb):
    result = src.create_database_collection(testdb, "public")
    assert result["status"] == "registry_only"


# ---------------------------------------------------------------------------
# Entity lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def users_table(src, testdb):
    src.create_database_collection_entity(
        testdb, "public", "users",
        properties={
            "cols_definition": [
                {"name": "id",    "type": "INT"},
                {"name": "name",  "type": "VARCHAR(100)"},
                {"name": "email", "type": "VARCHAR(200)"},
                {"name": "age",   "type": "INT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    return testdb, "public", "users"


@skip_no_mysql
def test_create_entity(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    assert entity in entities


@skip_no_mysql
def test_create_entity_skips_when_exists(src, users_table):
    db, col, entity = users_table
    result = src.create_database_collection_entity(
        db, col, entity,
        properties={"cols_definition": [{"name": "id", "type": "INT"}], "primary_key": ["id"]},
        overwrite=False,
    )
    assert result["status"] == "skipped"


@skip_no_mysql
def test_create_entity_overwrite(src, users_table):
    db, col, entity = users_table
    result = src.create_database_collection_entity(
        db, col, entity,
        properties={"cols_definition": [{"name": "id", "type": "INT"}], "primary_key": ["id"]},
        overwrite=True,
    )
    assert result["status"] == "success"


@skip_no_mysql
def test_create_entity_missing_cols_definition_raises(src, testdb):
    with pytest.raises(ValueError, match="cols_definition"):
        src.create_database_collection_entity(testdb, "public", "bad", properties={})


# ---------------------------------------------------------------------------
# Entity introspection
# ---------------------------------------------------------------------------

@skip_no_mysql
def test_fetch_entities_column_names(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    attrs = entities[entity]["contents"]["attributes"]
    assert "id" in attrs
    assert "name" in attrs
    assert "email" in attrs
    assert "age" in attrs


@skip_no_mysql
def test_fetch_entities_column_type(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    assert entities[entity]["contents"]["attributes"]["id"]["info"]["type"] == "int"


@skip_no_mysql
def test_fetch_entities_enum_values(src, testdb):
    src.create_database_collection_entity(
        testdb, "public", "statuses",
        properties={
            "cols_definition": [
                {"name": "id",     "type": "INT"},
                {"name": "status", "type": "ENUM('active','inactive','pending')"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    entities = src.fetch_database_collection_entities(testdb, "public")
    attr = entities["statuses"]["contents"]["attributes"]["status"]
    assert set(attr["info"]["values"]) == {"active", "inactive", "pending"}


# ---------------------------------------------------------------------------
# Entity stats
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_table(src, testdb):
    src.create_database_collection_entity(
        testdb, "public", "products",
        properties={
            "cols_definition": [
                {"name": "id",    "type": "INT"},
                {"name": "name",  "type": "VARCHAR(100)"},
                {"name": "price", "type": "FLOAT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    conn = src._db_connect(testdb)
    cur = conn.cursor()
    for i in range(1, 6):
        cur.execute(
            "INSERT INTO `products` VALUES (%s, %s, %s);",
            (i, f"product_{i}", float(i * 9.99)),
        )
    conn.commit()
    cur.close()
    src._db_disconnect(conn)
    return testdb, "public", "products"


@skip_no_mysql
def test_fetch_entity_stats_row_count(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_entity_stats(db, col, entity)
    assert stats["row_count"] == 5


# ---------------------------------------------------------------------------
# Attribute stats
# ---------------------------------------------------------------------------

@skip_no_mysql
def test_fetch_property_stats_integer(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_property_stats(db, col, entity, "id")
    assert stats["count"] == 5
    assert stats["distinct_count"] == 5
    assert stats["null_count"] == 0
    assert stats["min"] is not None
    assert stats["max"] is not None


@skip_no_mysql
def test_fetch_property_stats_text(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_property_stats(db, col, entity, "name")
    assert stats["count"] == 5
    assert len(stats["sample_values"]) > 0
    assert stats["min"] is None  # VARCHAR not in numeric/date set


@skip_no_mysql
def test_fetch_property_stats_null_count(src, testdb):
    src.create_database_collection_entity(
        testdb, "public", "sparse",
        properties={
            "cols_definition": [
                {"name": "id",  "type": "INT"},
                {"name": "val", "type": "VARCHAR(50)"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    conn = src._db_connect(testdb)
    cur = conn.cursor()
    for q in [
        ("INSERT INTO sparse VALUES (%s, %s);", (1, "x")),
        ("INSERT INTO sparse VALUES (%s, %s);", (2, None)),
        ("INSERT INTO sparse VALUES (%s, %s);", (3, None)),
    ]:
        cur.execute(*q)
    conn.commit()
    cur.close()
    src._db_disconnect(conn)

    stats = src.fetch_property_stats(testdb, "public", "sparse", "val")
    assert stats["null_count"] == 2
    assert stats["distinct_count"] == 1


@skip_no_mysql
def test_fetch_property_stats_most_common_vals(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_property_stats(db, col, entity, "id")
    assert isinstance(stats["most_common_vals"], list)


# ---------------------------------------------------------------------------
# import_data
# ---------------------------------------------------------------------------

@pytest.fixture
def import_table(src, testdb):
    """Create a simple items table for import_data tests."""
    src.create_database_collection_entity(
        testdb, "public", "items",
        properties={
            "cols_definition": [
                {"name": "id",   "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
            ],
        },
        overwrite=True,
    )
    return testdb, "public", "items"


@pytest.fixture
def file_src(tmp_path):
    """FileSource with a two-row items.csv."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files"
    d.mkdir()
    pd.DataFrame([{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]).to_csv(
        d / "items.csv", index=False
    )
    return FileSource("files", directory=str(d))


@skip_no_mysql
def test_import_data_requires_entity(src, testdb, file_src):
    with pytest.raises(ValueError, match="entity"):
        src.import_data(file_src, collection="items", database=testdb)


@skip_no_mysql
def test_import_data_inserts_rows(src, import_table, file_src):
    db, col, entity = import_table
    result = src.import_data(file_src, collection=entity, database=db, entity=entity)
    assert result["status"] == "success"
    assert result["rows_imported"] == 2
    rows = src.execute_query(f"SELECT * FROM `{entity}`", database=db)
    assert len(rows) == 2


@skip_no_mysql
def test_import_data_append_adds_rows(src, import_table, file_src):
    db, col, entity = import_table
    src.import_data(file_src, collection=entity, database=db, entity=entity)
    src.import_data(file_src, collection=entity, database=db, entity=entity, mode="append")
    rows = src.execute_query(f"SELECT * FROM `{entity}`", database=db)
    assert len(rows) == 4


@skip_no_mysql
def test_import_data_overwrite_truncates(src, import_table, file_src):
    db, col, entity = import_table
    src.import_data(file_src, collection=entity, database=db, entity=entity)
    src.import_data(file_src, collection=entity, database=db, entity=entity, mode="overwrite")
    rows = src.execute_query(f"SELECT * FROM `{entity}`", database=db)
    assert len(rows) == 2


@skip_no_mysql
def test_import_data_empty_source_returns_zero(src, import_table, tmp_path):
    from blue_data.source.file.file_source import FileSource

    db, col, entity = import_table
    empty_src = FileSource("empty", directory=str(tmp_path / "empty"))
    result = src.import_data(empty_src, collection=entity, database=db, entity=entity)
    assert result["status"] == "success"
    assert result["rows_imported"] == 0


@skip_no_mysql
def test_import_data_e2e_filesource_to_mysql(src, testdb, tmp_path):
    """CSV file → FileSource → MySQLDBSource round-trip."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files"
    d.mkdir()
    pd.DataFrame([
        {"id": 1, "product": "apple",  "price": 1.2},
        {"id": 2, "product": "banana", "price": 0.5},
        {"id": 3, "product": "cherry", "price": 3.0},
    ]).to_csv(d / "products.csv", index=False)

    src.create_database_collection_entity(
        testdb, "public", "products",
        properties={
            "cols_definition": [
                {"name": "id",      "type": "INTEGER"},
                {"name": "product", "type": "TEXT"},
                {"name": "price",   "type": "FLOAT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )

    file_src = FileSource("files", directory=str(d))
    result = src.import_data(file_src, collection="products", database=testdb, entity="products")
    assert result["rows_imported"] == 3

    rows = src.execute_query("SELECT * FROM `products` ORDER BY price", database=testdb)
    assert rows[0]["product"] == "banana"
    assert float(rows[2]["price"]) == 3.0
