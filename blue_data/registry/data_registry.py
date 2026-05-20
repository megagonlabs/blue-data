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

    # ---------- hierarchy property helpers ----------

    def get_source_database_property(
        self,
        source: str,
        database: str,
        key: str,
    ):
        return self.get_record_property(
            database,
            "database",
            f"/source/{source}",
            key,
        )

    def set_source_database_property(
        self,
        source: str,
        database: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            database,
            "database",
            f"/source/{source}",
            key,
            value,
        )

    def get_source_database_collection_property(
        self,
        source: str,
        database: str,
        collection: str,
        key: str,
    ):
        return self.get_record_property(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            key,
        )

    def set_source_database_collection_property(
        self,
        source: str,
        database: str,
        collection: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            key,
            value,
        )

    def get_source_database_collection_entity_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        key: str,
    ):
        return self.get_record_property(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
        )

    def set_source_database_collection_entity_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
            value,
        )

    def get_source_database_collection_entity_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        key: str,
    ):
        return self.get_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            key,
        )

    def set_source_database_collection_entity_attribute_property(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            key,
            value,
        )

        # ---------- hierarchy description helpers ----------

    def get_source_database_description(
        self,
        source: str,
        database: str,
    ):
        return self.get_record_description(
            database,
            "database",
            f"/source/{source}",
        )

    def set_source_database_description(
        self,
        source: str,
        database: str,
        description: str,
    ):
        return self.set_record_description(
            database,
            "database",
            f"/source/{source}",
            description,
        )

    def get_source_database_collection_description(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.get_record_description(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
        )

    def set_source_database_collection_description(
        self,
        source: str,
        database: str,
        collection: str,
        description: str,
    ):
        return self.set_record_description(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            description,
        )

    def get_source_database_collection_entity_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        return self.get_record_description(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
        )

    def set_source_database_collection_entity_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str,
    ):
        return self.set_record_description(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            description,
        )

    def get_source_database_collection_entity_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        return self.get_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )

    def set_source_database_collection_entity_attribute_description(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str,
    ):
        return self.set_record_description(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description,
        )

    
    # ---------- sync helpers ----------

    def sync_source(self, source: str, recursive: bool = False):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        metadata = source_obj.fetch_metadata()
        if metadata:
            self.set_record_property(source, "source", "/", "metadata", metadata)

        databases = source_obj.fetch_databases()

        for database in databases:
            self.register_source_database(
                source=source,
                database=database,
            )

            if recursive:
                self.sync_source_database(
                    source=source,
                    database=database,
                    source_obj=source_obj,
                    recursive=recursive,
                )

    def sync_source_database(
        self,
        source: str,
        database: str,
        source_obj=None,
        recursive: bool = False,
    ):
        if source_obj is None:
            source_obj = self.get_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        metadata = source_obj.fetch_database_metadata(database)
        if metadata:
            self.set_source_database_property(
                source,
                database,
                "metadata",
                metadata,
            )

        collections = source_obj.fetch_database_collections(database)

        for collection in collections:
            self.register_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

            if recursive:
                self.sync_source_database_collection(
                    source=source,
                    database=database,
                    collection=collection,
                    source_obj=source_obj,
                )

    def sync_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        source_obj=None,
    ):
        if source_obj is None:
            source_obj = self.get_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        metadata = source_obj.fetch_database_collection_metadata(
            database,
            collection,
        )

        if metadata:
            self.set_source_database_collection_property(
                source,
                database,
                collection,
                "metadata",
                metadata,
            )

        entities = source_obj.fetch_database_collection_entities(
            database,
            collection,
        )

        for entity_name, entity_obj in entities.items():
            self.register_source_database_collection_entity(
                source=source,
                database=database,
                collection=collection,
                entity=entity_name,
                properties=entity_obj.get("properties", {}),
            )

            attributes = (
                entity_obj
                .get("contents", {})
                .get("attributes", {})
            )

            for attr_name, attr_props in attributes.items():
                self.register_source_database_collection_entity_attribute(
                    source=source,
                    database=database,
                    collection=collection,
                    entity=entity_name,
                    attribute=attr_name,
                    properties=attr_props,
                )

        relations = source_obj.fetch_database_collection_relations(
            database,
            collection,
        )

        for relation_name, relation_obj in relations.items():
            self.register_source_database_collection_relation(
                source=source,
                database=database,
                collection=collection,
                relation=relation_name,
                properties=relation_obj.get("properties", {}),
            )