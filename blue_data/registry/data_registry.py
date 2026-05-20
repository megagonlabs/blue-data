from __future__ import annotations

from blue_data.core.registry import Registry
from blue_data.core.source import DataSource


class DataRegistry(Registry):
    """Registry for managing data sources."""

    def __init__(self, name: str = "DATA_REGISTRY", store=None):
        super().__init__(name=name, store=store)
        self.sources: dict[str, DataSource] = {}

    def register_source(self, source: DataSource) -> None:
        self.sources[source.name] = source

        self.register_record(
            name=source.name,
            type="source",
            scope="/",
            description=f"{source.name} data source",
            properties=source.properties,
        )

    def get_source(self, name: str) -> DataSource | None:
        return self.sources.get(name)

    def list_sources(self) -> list[str]:
        return list(self.sources.keys())

    def execute_query(
        self,
        source: str,
        query,
        database: str | None = None,
        collection: str | None = None,
        optional_properties: dict | None = None,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        return source_obj.execute_query(
            query=query,
            database=database,
            collection=collection,
            optional_properties=optional_properties or {},
        )

    
    # ---------- hierarchy helpers ----------

    def register_source_database(
        self,
        source: str,
        database: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=database,
            type="database",
            scope=f"/source/{source}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=collection,
            type="collection",
            scope=f"/source/{source}/database/{database}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=entity,
            type="entity",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=attribute,
            type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=relation,
            type="relation",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties or {},
        )

    def register_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        description: str = "",
        properties: dict | None = None,
    ):
        return self.register_record(
            name=attribute,
            type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            description=description,
            properties=properties or {},
        )

    def list_source_databases(self, source: str):
        return self.list_records(
            record_type="database",
            scope=f"/source/{source}",
        )

    def list_database_collections(
        self,
        source: str,
        database: str,
    ):
        return self.list_records(
            record_type="collection",
            scope=f"/source/{source}/database/{database}",
        )

    def list_collection_entities(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.list_records(
            record_type="entity",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
        )

    def list_entity_attributes(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        return self.list_records(
            record_type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )