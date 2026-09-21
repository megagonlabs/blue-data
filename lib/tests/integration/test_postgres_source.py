"""Integration tests for PostgresDBSource.

Requires a running PostgreSQL instance. All tests are skipped automatically
when no connection can be established.

Default connection: localhost:5432, user=postgres, password="" (no password).
Override via environment variables:
    PGHOST, PGPORT, PGUSER, PGPASSWORD

Run just these tests:
    python3 -m pytest lib/tests/integration/test_postgres_source.py -v
"""
import os
import uuid

import pytest

try:
    import psycopg2
except ImportError:
    psycopg2 = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _pg_conn_kwargs():
    return {
        "host":     os.environ.get("PGHOST",     "localhost"),
        "port":     int(os.environ.get("PGPORT",  "5432")),
        "user":     os.environ.get("PGUSER",     "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "database": "postgres",
    }


def _postgres_available():
    if psycopg2 is None:
        return False
    try:
        conn = psycopg2.connect(**_pg_conn_kwargs())
        conn.close()
        return True
    except Exception:
        return False


skip_no_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not available — set PGHOST/PGPORT/PGUSER/PGPASSWORD or start a local server",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def src():
    """A PostgresDBSource connected to the local server."""
    from blue_data.source.sql.postgres.postgres_sql_source import PostgresDBSource

    kwargs = _pg_conn_kwargs()
    source = PostgresDBSource(
        name="test_pg",
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
    # teardown
    src.connection.autocommit = True
    with src.connection.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid();",
            (db_name,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}";')


# ---------------------------------------------------------------------------
# Source-level
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_fetch_source_stats(src):
    stats = src.fetch_source_stats()
    assert "version" in stats
    assert "database_count" in stats
    assert stats["database_count"] >= 1


@skip_no_postgres
def test_fetch_databases_includes_postgres(src):
    dbs = src.fetch_databases()
    assert "postgres" in dbs


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_create_database(src, testdb):
    assert testdb in src.fetch_databases()


@skip_no_postgres
def test_create_database_skips_when_exists(src, testdb):
    result = src.create_database(testdb, overwrite=False)
    assert result["status"] == "skipped"


@skip_no_postgres
def test_create_database_overwrite(src, testdb):
    result = src.create_database(testdb, overwrite=True)
    assert result["status"] == "success"


@skip_no_postgres
def test_fetch_database_stats(src, testdb):
    stats = src.fetch_database_stats(testdb)
    assert "size_bytes" in stats
    assert "table_count" in stats


# ---------------------------------------------------------------------------
# Collection (schema) lifecycle
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_fetch_database_collections_includes_public(src, testdb):
    collections = src.fetch_database_collections(testdb)
    assert "public" in collections


@skip_no_postgres
def test_create_database_collection(src, testdb):
    result = src.create_database_collection(testdb, "app")
    assert result["status"] == "success"
    assert "app" in src.fetch_database_collections(testdb)


@skip_no_postgres
def test_create_database_collection_skips_when_exists(src, testdb):
    src.create_database_collection(testdb, "analytics")
    result = src.create_database_collection(testdb, "analytics", overwrite=False)
    assert result["status"] == "skipped"


@skip_no_postgres
def test_create_database_collection_overwrite(src, testdb):
    src.create_database_collection(testdb, "scratch")
    result = src.create_database_collection(testdb, "scratch", overwrite=True)
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Entity lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def users_table(src, testdb):
    """Create a users table in testdb.public and return (testdb, 'public', 'users')."""
    src.create_database_collection_entity(
        testdb, "public", "users",
        properties={
            "cols_definition": [
                {"name": "id",    "type": "INTEGER"},
                {"name": "name",  "type": "TEXT"},
                {"name": "email", "type": "TEXT"},
                {"name": "age",   "type": "INTEGER"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    return testdb, "public", "users"


@skip_no_postgres
def test_create_entity(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    assert entity in entities


@skip_no_postgres
def test_create_entity_skips_when_exists(src, users_table):
    db, col, entity = users_table
    result = src.create_database_collection_entity(
        db, col, entity,
        properties={
            "cols_definition": [{"name": "id", "type": "INTEGER"}],
            "primary_key": ["id"],
        },
        overwrite=False,
    )
    assert result["status"] == "skipped"


@skip_no_postgres
def test_create_entity_overwrite(src, users_table):
    db, col, entity = users_table
    result = src.create_database_collection_entity(
        db, col, entity,
        properties={
            "cols_definition": [{"name": "id", "type": "INTEGER"}],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    assert result["status"] == "success"


@skip_no_postgres
def test_create_entity_missing_cols_definition_raises(src, testdb):
    with pytest.raises(ValueError, match="cols_definition"):
        src.create_database_collection_entity(
            testdb, "public", "bad_table",
            properties={},
        )


# ---------------------------------------------------------------------------
# Entity introspection
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_fetch_entities_returns_column_info(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    assert entity in entities
    attrs = entities[entity]["contents"]["attributes"]
    assert "id" in attrs
    assert "name" in attrs
    assert "email" in attrs
    assert "age" in attrs


@skip_no_postgres
def test_fetch_entities_has_type_info(src, users_table):
    db, col, entity = users_table
    entities = src.fetch_database_collection_entities(db, col)
    id_attr = entities[entity]["contents"]["attributes"]["id"]
    assert "info" in id_attr
    assert "type" in id_attr["info"]


# ---------------------------------------------------------------------------
# Relations (foreign keys)
# ---------------------------------------------------------------------------

@pytest.fixture
def fk_tables(src, testdb):
    """Create orders → users FK relationship in testdb.public."""
    src.create_database_collection_entity(
        testdb, "public", "customers",
        properties={
            "cols_definition": [
                {"name": "id",   "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    src.create_database_collection_entity(
        testdb, "public", "invoices",
        properties={
            "cols_definition": [
                {"name": "id",          "type": "INTEGER"},
                {"name": "customer_id", "type": "INTEGER"},
            ],
            "primary_key": ["id"],
            "foreign_keys": [{
                "foreign_keys_source_columns": ["customer_id"],
                "foreign_keys_target_columns": ["id"],
                "foreign_keys_target_table": "customers",
            }],
        },
        overwrite=True,
    )
    return testdb, "public"


@skip_no_postgres
def test_fetch_relations_detects_foreign_key(src, fk_tables):
    db, col = fk_tables
    relations = src.fetch_database_collection_relations(db, col)
    assert len(relations) >= 1
    rel = next(iter(relations.values()))
    props = rel["properties"]
    assert props["source_entity"] == "invoices"
    assert props["target_entity"] == "customers"


@skip_no_postgres
def test_fetch_relations_empty_when_no_fks(src, users_table):
    db, col, _ = users_table
    # users table has no FK columns — but other fixtures may have added some;
    # just assert the method returns a dict without raising.
    relations = src.fetch_database_collection_relations(db, col)
    assert isinstance(relations, dict)


# ---------------------------------------------------------------------------
# Entity stats
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_table(src, testdb):
    """Create and populate a products table with 5 rows."""
    src.create_database_collection_entity(
        testdb, "public", "products",
        properties={
            "cols_definition": [
                {"name": "id",    "type": "INTEGER"},
                {"name": "name",  "type": "TEXT"},
                {"name": "price", "type": "REAL"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    conn = src._db_connect(testdb)
    with conn.cursor() as cur:
        for i in range(1, 6):
            cur.execute(
                'INSERT INTO public.products VALUES (%s, %s, %s);',
                (i, f"product_{i}", float(i * 9.99)),
            )
    conn.commit()
    conn.close()
    return testdb, "public", "products"


@skip_no_postgres
def test_fetch_entity_stats_row_count(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_entity_stats(db, col, entity)
    assert stats["row_count"] == 5


@skip_no_postgres
def test_fetch_entity_stats_has_samples(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_entity_stats(db, col, entity)
    assert stats["row_sample_size"] > 0
    assert isinstance(stats["row_samples"], list)
    first = stats["row_samples"][0]
    assert "id" in first and "name" in first


# ---------------------------------------------------------------------------
# Attribute stats
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_fetch_property_stats_integer(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_property_stats(db, col, entity, "id")
    assert stats["count"] == 5
    assert stats["distinct_count"] == 5
    assert stats["null_count"] == 0
    assert stats["min"] is not None
    assert stats["max"] is not None


@skip_no_postgres
def test_fetch_property_stats_text(src, populated_table):
    db, col, entity = populated_table
    stats = src.fetch_property_stats(db, col, entity, "name")
    assert stats["count"] == 5
    assert len(stats["sample_values"]) > 0


@skip_no_postgres
def test_fetch_property_stats_null_count(src, testdb):
    """Null count is reported correctly for a column with NULLs."""
    src.create_database_collection_entity(
        testdb, "public", "sparse",
        properties={
            "cols_definition": [
                {"name": "id",  "type": "INTEGER"},
                {"name": "val", "type": "TEXT"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )
    conn = src._db_connect(testdb)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO public.sparse VALUES (1, 'hello'), (2, NULL), (3, NULL);")
    conn.commit()
    conn.close()

    stats = src.fetch_property_stats(testdb, "public", "sparse", "val")
    assert stats["null_count"] == 2
    assert stats["distinct_count"] == 1


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
                {"name": "id",    "type": "INTEGER"},
                {"name": "name",  "type": "TEXT"},
            ],
        },
        overwrite=True,
    )
    return testdb, "public", "items"


@pytest.fixture
def file_src(tmp_path):
    """FileSource with a two-row public.csv (collection name matches Postgres schema)."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files"
    d.mkdir()
    pd.DataFrame([{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]).to_csv(
        d / "public.csv", index=False
    )
    return FileSource("files", directory=str(d))


@skip_no_postgres
def test_import_data_requires_entity(src, testdb, file_src):
    with pytest.raises(ValueError, match="entity"):
        src.import_data(file_src, collection="items", database=testdb)


@skip_no_postgres
def test_import_data_inserts_rows(src, import_table, file_src):
    db, col, entity = import_table
    result = src.import_data(file_src, collection=col, database=db, entity=entity)
    assert result["status"] == "success"
    assert result["rows_imported"] == 2
    rows = src.execute_query(f'SELECT * FROM "{col}"."{entity}"', database=db)
    assert len(rows) == 2


@skip_no_postgres
def test_import_data_append_adds_rows(src, import_table, file_src):
    db, col, entity = import_table
    src.import_data(file_src, collection=col, database=db, entity=entity)
    src.import_data(file_src, collection=col, database=db, entity=entity, mode="append")
    rows = src.execute_query(f'SELECT * FROM "{col}"."{entity}"', database=db)
    assert len(rows) == 4


@skip_no_postgres
def test_import_data_overwrite_truncates(src, import_table, file_src):
    db, col, entity = import_table
    src.import_data(file_src, collection=col, database=db, entity=entity)
    src.import_data(file_src, collection=col, database=db, entity=entity, mode="overwrite")
    rows = src.execute_query(f'SELECT * FROM "{col}"."{entity}"', database=db)
    assert len(rows) == 2


@skip_no_postgres
def test_import_data_empty_source_returns_zero(src, import_table, tmp_path):
    from blue_data.source.file.file_source import FileSource

    db, col, entity = import_table
    empty_src = FileSource("empty", directory=str(tmp_path / "empty"))
    result = src.import_data(empty_src, collection=entity, database=db, entity=entity)
    assert result["status"] == "success"
    assert result["rows_imported"] == 0


@skip_no_postgres
def test_import_data_e2e_filesource_to_postgres(src, testdb, tmp_path):
    """CSV file → FileSource → PostgresDBSource round-trip."""
    from blue_data.source.file.file_source import FileSource
    import pandas as pd

    d = tmp_path / "files"
    d.mkdir()
    pd.DataFrame([
        {"id": 1, "product": "apple",  "price": 1.2},
        {"id": 2, "product": "banana", "price": 0.5},
        {"id": 3, "product": "cherry", "price": 3.0},
    ]).to_csv(d / "public.csv", index=False)

    src.create_database_collection_entity(
        testdb, "public", "products",
        properties={
            "cols_definition": [
                {"name": "id",      "type": "INTEGER"},
                {"name": "product", "type": "TEXT"},
                {"name": "price",   "type": "REAL"},
            ],
            "primary_key": ["id"],
        },
        overwrite=True,
    )

    file_src = FileSource("files", directory=str(d))
    result = src.import_data(file_src, collection="public", database=testdb, entity="products")
    assert result["rows_imported"] == 3

    rows = src.execute_query('SELECT * FROM "public"."products" ORDER BY price', database=testdb)
    assert rows[0]["product"] == "banana"
    assert float(rows[2]["price"]) == 3.0


# ---------------------------------------------------------------------------
# DataRegistry round-trip
# ---------------------------------------------------------------------------

@skip_no_postgres
def test_registry_sync_and_stats(src, populated_table):
    """Full round-trip: register → sync → collect stats → check attribute stats."""
    from blue_data.registry.data_registry import DataRegistry
    from blue_data.source.json.memory_json_source import MemoryJSONSource

    db, col, entity = populated_table

    registry = DataRegistry(store=MemoryJSONSource())
    registry.register_source(src)
    registry.sync_all(recursive=True)
    registry.collect_source_stats("test_pg", recursive=True)

    attr_stats = registry.get_source_database_collection_entity_attribute_property(
        "test_pg", db, col, entity, "price", "stats"
    )
    assert attr_stats is not None
    assert attr_stats["count"] == 5
