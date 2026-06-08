from registry.data_registry import DataRegistry
from source.sql.sqlite.sqlite_sql_source import SQLiteDBSource


registry = DataRegistry()

source = SQLiteDBSource(
    name="sqlite",
    properties={
        "connection": {
            "database_directory": "/tmp/blue-data-sqlite"
        }
    },
)

registry.register_source(source)

print("Registered sources:", registry.list_sources())

source.create_database("test_db", overwrite=True)

registry.execute_query(
    source="sqlite",
    database="test_db",
    query="""
    CREATE TABLE people (
        id INTEGER PRIMARY KEY,
        name TEXT
    );
    """,
    optional_properties={"commit": True},
)

registry.execute_query(
    source="sqlite",
    database="test_db",
    query="INSERT INTO people (name) VALUES ('Alice');",
    optional_properties={"commit": True},
)

rows = registry.execute_query(
    source="sqlite",
    database="test_db",
    query="SELECT * FROM people;",
)

print("Query result:", rows)