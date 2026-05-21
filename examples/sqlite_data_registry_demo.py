from blue_data.registry.data_registry import DataRegistry
from blue_data.sources.memory_json_source import MemoryJSONSource
from blue_data.sources.sqlite_source import SQLiteDBSource


registry = DataRegistry(store=MemoryJSONSource())

source = SQLiteDBSource(
    name="sqlite",
    properties={"connection": {"database_directory": "/tmp/blue-data-demo"}},
)

registry.register_source(source)

registry.create_source_database("sqlite", "demo_db", overwrite=True)

registry.create_source_database_collection_entity(
    "sqlite",
    "demo_db",
    "public",
    "users",
    creation_properties={
        "cols_definition": [
            {"name": "id", "type": "INTEGER"},
            {"name": "age", "type": "INTEGER"},
            {"name": "name", "type": "TEXT"},
        ],
        "primary_key": ["id"],
    },
    overwrite=True,
)

registry.execute_query(
    source="sqlite",
    database="demo_db",
    query="INSERT INTO users VALUES (1, 25, 'Alice');",
    optional_properties={"commit": True},
)

registry.sync_all(recursive=True)
registry.collect_source_stats("sqlite", recursive=True)
registry.enrich_source("sqlite")

print(registry.get_data_source_schema("sqlite", "demo_db", "public", format="json"))

print(
    registry.get_source_database_collection_entity_attribute_property(
        "sqlite",
        "demo_db",
        "public",
        "users",
        "age",
        "value_semantics",
    )
)