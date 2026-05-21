from __future__ import annotations

from blue_data.core.registry import Registry
from blue_data.core.source import DataSource
from blue_data.enrichment.value_semantics.semantic_types import SemanticTypeInferencer


class DataRegistry(Registry):
    """Registry for managing data sources."""

    def __init__(self, name: str = "DATA_REGISTRY", store=None):
        super().__init__(name=name, store=store)
        self.sources: dict[str, DataSource] = {}
        self.semantic_type_inferencer = SemanticTypeInferencer()

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

        fetched_databases = set(source_obj.fetch_databases())
        registry_databases = {
            record["name"]
            for record in self.list_source_databases(source)
        }

        adds = fetched_databases - registry_databases
        removes = registry_databases - fetched_databases
        merges = fetched_databases & registry_databases

        for database in adds:
            self.register_source_database(
                source=source,
                database=database,
            )

        for database in removes:
            self.deregister_source_database(
                source=source,
                database=database,
            )

        databases_to_sync = fetched_databases if recursive else adds | merges

        for database in databases_to_sync:
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

        fetched_collections = set(
            source_obj.fetch_database_collections(database)
        )

        registry_collections = {
            record["name"]
            for record in self.list_database_collections(source, database)
        }

        adds = fetched_collections - registry_collections
        removes = registry_collections - fetched_collections
        merges = fetched_collections & registry_collections

        for collection in adds:
            self.register_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        for collection in removes:
            self.deregister_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        collections_to_sync = fetched_collections if recursive else adds | merges

        for collection in collections_to_sync:
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

        # ---------- entities ----------
        entities = source_obj.fetch_database_collection_entities(
            database,
            collection,
        )

        fetched_entities = set(entities.keys())

        registry_entities = {
            record["name"]
            for record in self.list_collection_entities(
                source,
                database,
                collection,
            )
        }

        entity_adds = fetched_entities - registry_entities
        entity_removes = registry_entities - fetched_entities
        entity_merges = fetched_entities & registry_entities

        for entity_name in entity_adds:
            entity_obj = entities[entity_name]

            self.register_source_database_collection_entity(
                source=source,
                database=database,
                collection=collection,
                entity=entity_name,
                properties=entity_obj.get("properties", {}),
            )

        for entity_name in entity_removes:
            self.deregister_source_database_collection_entity(
                source,
                database,
                collection,
                entity_name,
            )

        for entity_name in entity_adds | entity_merges:
            entity_obj = entities[entity_name]

            self.update_source_database_collection_entity(
                source,
                database,
                collection,
                entity_name,
                properties=entity_obj.get("properties", {}),
            )

            attributes = (
                entity_obj
                .get("contents", {})
                .get("attributes", {})
            )

            fetched_attributes = set(attributes.keys())

            registry_attributes = {
                record["name"]
                for record in self.list_entity_attributes(
                    source,
                    database,
                    collection,
                    entity_name,
                )
            }

            attr_adds = fetched_attributes - registry_attributes
            attr_removes = registry_attributes - fetched_attributes
            attr_merges = fetched_attributes & registry_attributes

            for attr_name in attr_adds:
                self.register_source_database_collection_entity_attribute(
                    source=source,
                    database=database,
                    collection=collection,
                    entity=entity_name,
                    attribute=attr_name,
                    properties=attributes[attr_name],
                )

            for attr_name in attr_removes:
                self.deregister_source_database_collection_entity_attribute(
                    source,
                    database,
                    collection,
                    entity_name,
                    attr_name,
                )

            for attr_name in attr_adds | attr_merges:
                self.update_source_database_collection_entity_attribute(
                    source,
                    database,
                    collection,
                    entity_name,
                    attr_name,
                    properties=attributes[attr_name],
                )

        # ---------- relations ----------
        relations = source_obj.fetch_database_collection_relations(
            database,
            collection,
        )

        fetched_relations = set(relations.keys())

        registry_relations = {
            record["name"]
            for record in self.list_collection_relations(
                source,
                database,
                collection,
            )
        }

        relation_adds = fetched_relations - registry_relations
        relation_removes = registry_relations - fetched_relations
        relation_merges = fetched_relations & registry_relations

        for relation_name in relation_adds:
            relation_obj = relations[relation_name]

            self.register_source_database_collection_relation(
                source=source,
                database=database,
                collection=collection,
                relation=relation_name,
                properties=relation_obj.get("properties", {}),
            )

        for relation_name in relation_removes:
            self.deregister_source_database_collection_relation(
                source,
                database,
                collection,
                relation_name,
            )

        for relation_name in relation_adds | relation_merges:
            relation_obj = relations[relation_name]

            self.update_source_database_collection_relation(
                source,
                database,
                collection,
                relation_name,
                properties=relation_obj.get("properties", {}),
            )

            relation_attributes = (
                relation_obj
                .get("contents", {})
                .get("attributes", {})
            )

            fetched_relation_attributes = set(relation_attributes.keys())

            registry_relation_attributes = {
                record["name"]
                for record in self.get_source_database_collection_relation_attributes(
                    source,
                    database,
                    collection,
                    relation_name,
                )
            } if hasattr(self, "get_source_database_collection_relation_attributes") else set()

            rel_attr_adds = fetched_relation_attributes - registry_relation_attributes
            rel_attr_removes = registry_relation_attributes - fetched_relation_attributes
            rel_attr_merges = fetched_relation_attributes & registry_relation_attributes

            for attr_name in rel_attr_adds:
                self.register_source_database_collection_relation_attribute(
                    source=source,
                    database=database,
                    collection=collection,
                    relation=relation_name,
                    attribute=attr_name,
                    properties=relation_attributes[attr_name],
                )

            for attr_name in rel_attr_removes:
                self.deregister_source_database_collection_relation_attribute(
                    source,
                    database,
                    collection,
                    relation_name,
                    attr_name,
                )

            for attr_name in rel_attr_adds | rel_attr_merges:
                self.update_source_database_collection_relation_attribute(
                    source,
                    database,
                    collection,
                    relation_name,
                    attr_name,
                    properties=relation_attributes[attr_name],
                )

    def collect_source_database_stats(
        self,
        source: str,
        database: str,
    ):
        source_obj = self.get_source(source)
    
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_database_stats(database)

        if stats:
            self.set_source_database_property(
                source,
                database,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_stats(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        source_obj = self.get_source(source)

        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        entities = self.list_collection_entities(source, database, collection)
        relations = self.list_collection_relations(source, database, collection) if hasattr(self, "list_collection_relations") else []

        stats = source_obj.fetch_collection_stats(
            database,
            collection,
            entities,
            relations,
        )

        if stats:
            self.set_source_database_collection_property(
                source,
                database,
                collection,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_entity_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        source_obj = self.get_source(source)
        
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_entity_stats(
            database,
            collection,
            entity,
        )

        if stats:
            self.set_source_database_collection_entity_property(
                source,
                database,
                collection,
                entity,
                "stats",
                stats,
            )

        return stats

    def collect_source_database_collection_entity_attribute_stats(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        sample_limit: int = 10,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_property_stats(
            database,
            collection,
            entity,
            attribute,
            sample_limit=sample_limit,
        )

        if stats:
            self.set_source_database_collection_entity_attribute_property(
                source,
                database,
                collection,
                entity,
                attribute,
                "stats",
                stats,
            )

        return stats

    def collect_source_stats(
        self,
        source: str,
        recursive: bool = False,
        sample_limit: int = 10,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        stats = source_obj.fetch_source_stats()

        if stats:
            self.set_record_property(
                source,
                "source",
                "/",
                "stats",
                stats,
            )

        if recursive:
            for database_record in self.list_source_databases(source):
                database = database_record["name"]

                self.collect_source_database_stats(
                    source,
                    database,
                )

                for collection_record in self.list_database_collections(
                    source,
                    database,
                ):
                    collection = collection_record["name"]

                    self.collect_source_database_collection_stats(
                        source,
                        database,
                        collection,
                    )

                    for entity_record in self.list_collection_entities(
                        source,
                        database,
                        collection,
                    ):
                        entity = entity_record["name"]

                        self.collect_source_database_collection_entity_stats(
                            source,
                            database,
                            collection,
                            entity,
                        )

                        for attribute_record in self.list_entity_attributes(
                            source,
                            database,
                            collection,
                            entity,
                        ):
                            attribute = attribute_record["name"]

                            self.collect_source_database_collection_entity_attribute_stats(
                                source,
                                database,
                                collection,
                                entity,
                                attribute,
                                sample_limit=sample_limit,
                            )

        return stats
    
    def list_collection_relations(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.list_records(
            record_type="relation",
            scope=f"/source/{source}/database/{database}/collection/{collection}",
        )

    def enrich_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        stats = self.get_source_database_collection_entity_attribute_property(
            source,
            database,
            collection,
            entity,
            attribute,
            "stats",
        )

        if not stats:
            stats = self.collect_source_database_collection_entity_attribute_stats(
                source,
                database,
                collection,
                entity,
                attribute,
            )

        values = stats.get("sample_values", [])
        semantic_info = self.semantic_type_inferencer.infer(values)

        self.set_source_database_collection_entity_attribute_property(
            source,
            database,
            collection,
            entity,
            attribute,
            "value_semantics",
            semantic_info,
        )

        return semantic_info

    def enrich_source(self, source: str):
        for database_record in self.list_source_databases(source):
            database = database_record["name"]

            for collection_record in self.list_database_collections(source, database):
                collection = collection_record["name"]

                for entity_record in self.list_collection_entities(source, database, collection):
                    entity = entity_record["name"]

                    for attribute_record in self.list_entity_attributes(
                        source, database, collection, entity
                    ):
                        attribute = attribute_record["name"]

                        self.enrich_source_database_collection_entity_attribute(
                            source,
                            database,
                            collection,
                            entity,
                            attribute,
                        )

    # ---------- source record helpers ----------

    def get_source_record(self, source: str):
        return self.get_record(source, "source", "/")

    def update_source(
        self,
        source: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            source,
            "source",
            "/",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source(self, source: str):
        record = self.get_source_record(source)
        self.sources.pop(source, None)
        return self.deregister(record)
    

    # ---------- database update/deregister/get helpers ----------

    def get_source_database(self, source: str, database: str):
        return self.get_record(
            database,
            "database",
            f"/source/{source}",
        )

    def update_source_database(
        self,
        source: str,
        database: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            database,
            "database",
            f"/source/{source}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database(self, source: str, database: str):
        record = self.get_source_database(source, database)
        return self.deregister(record)
    
    # ---------- collection update/deregister/get helpers ----------

    def get_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        return self.get_record(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
        )

    def update_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            collection,
            "collection",
            f"/source/{source}/database/{database}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
    ):
        record = self.get_source_database_collection(source, database, collection)
        return self.deregister(record)
    
    # ---------- entity update/deregister/get helpers ----------

    def get_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        return self.get_record(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
        )

    def update_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            entity,
            "entity",
            f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
    ):
        record = self.get_source_database_collection_entity(
            source,
            database,
            collection,
            entity,
        )
        return self.deregister(record)
    
    # ---------- entity attribute update/deregister/get helpers ----------
    def get_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        return self.get_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
        )

    def update_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/entity/{entity}",
            description=description,
            properties=properties,
            icon=icon,
        )

    def deregister_source_database_collection_entity_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        attribute: str,
    ):
        record = self.get_source_database_collection_entity_attribute(
            source,
            database,
            collection,
            entity,
            attribute,
        )
        return self.deregister(record)
    
    # ---------- create operation helpers ----------

    def create_source_database(
        self,
        source: str,
        database: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database(source, database) and not overwrite:
            return None

        if self.get_source_database(source, database) and overwrite:
            self.deregister_source_database(source, database)

        result = source_obj.create_database(
            database,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source(source, recursive=recursive)

            for key, value in (properties or {}).items():
                self.set_source_database_property(
                    source,
                    database,
                    key,
                    value,
                )

        return result

    def create_source_database_collection(
        self,
        source: str,
        database: str,
        collection: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database_collection(source, database, collection) and not overwrite:
            return None

        if self.get_source_database_collection(source, database, collection) and overwrite:
            self.deregister_source_database_collection(source, database, collection)

        result = source_obj.create_database_collection(
            database,
            collection,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database(
                source,
                database,
                source_obj=source_obj,
                recursive=recursive,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_property(
                    source,
                    database,
                    collection,
                    key,
                    value,
                )

        return result

    def create_source_database_collection_entity(
        self,
        source: str,
        database: str,
        collection: str,
        entity: str,
        properties: dict | None = None,
        creation_properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        # Ensure parent database exists in registry
        if not self.get_source_database(source, database):
            self.register_source_database(
                source=source,
                database=database,
            )

        # Ensure parent collection exists in registry
        if not self.get_source_database_collection(source, database, collection):
            self.register_source_database_collection(
                source=source,
                database=database,
                collection=collection,
            )

        if self.get_source_database_collection_entity(source, database, collection, entity) and not overwrite:
            return None

        if self.get_source_database_collection_entity(source, database, collection, entity) and overwrite:
            self.deregister_source_database_collection_entity(
                source,
                database,
                collection,
                entity,
            )

        result = source_obj.create_database_collection_entity(
            database,
            collection,
            entity,
            properties=creation_properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database_collection(
                source,
                database,
                collection,
                source_obj=source_obj,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_entity_property(
                    source,
                    database,
                    collection,
                    entity,
                    key,
                    value,
                )

        return result
        
    def create_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        properties: dict | None = None,
        overwrite: bool = False,
        recursive: bool = False,
    ):
        source_obj = self.get_source(source)
        if source_obj is None:
            raise ValueError(f"Source not registered: {source}")

        if self.get_source_database_collection_relation(source, database, collection, relation) and not overwrite:
            return None

        if self.get_source_database_collection_relation(source, database, collection, relation) and overwrite:
            self.deregister_source_database_collection_relation(
                source,
                database,
                collection,
                relation,
            )

        result = source_obj.create_database_collection_relation(
            database,
            collection,
            relation,
            properties=properties or {},
            overwrite=overwrite,
        )

        if result and result.get("status") in {"success", "registry_only", "skipped"}:
            self.sync_source_database_collection(
                source,
                database,
                collection,
                source_obj=source_obj,
            )

            for key, value in (properties or {}).items():
                self.set_source_database_collection_relation_property(
                    source,
                    database,
                    collection,
                    relation,
                    key,
                    value,
                )

        return result

    def get_source_database_collection_relation_attributes(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        return self.list_records(
            record_type="attribute",
            scope=f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
        )

    # ---------- relation update/deregister/get helpers ----------

    def get_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        return self.get_record(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
        )


    def update_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            description=description,
            properties=properties,
            icon=icon,
        )


    def deregister_source_database_collection_relation(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        record = self.get_source_database_collection_relation(
            source,
            database,
            collection,
            relation,
        )
        return self.deregister(record)


    # ---------- relation property helpers ----------

    def get_source_database_collection_relation_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        key: str,
    ):
        return self.get_record_property(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
        )


    def set_source_database_collection_relation_property(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        key: str,
        value,
    ):
        return self.set_record_property(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            key,
            value,
        )


    # ---------- relation description helpers ----------

    def get_source_database_collection_relation_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
    ):
        return self.get_record_description(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
        )


    def set_source_database_collection_relation_description(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        description: str,
    ):
        return self.set_record_description(
            relation,
            "relation",
            f"/source/{source}/database/{database}/collection/{collection}",
            description,
        )    
    
    # ---------- relation attribute update/deregister/get helpers ----------

    def get_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
    ):
        return self.get_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
        )


    def update_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
        description: str | None = None,
        properties: dict | None = None,
        icon: str | None = None,
    ):
        return self.update_record(
            attribute,
            "attribute",
            f"/source/{source}/database/{database}/collection/{collection}/relation/{relation}",
            description=description,
            properties=properties,
            icon=icon,
        )


    def deregister_source_database_collection_relation_attribute(
        self,
        source: str,
        database: str,
        collection: str,
        relation: str,
        attribute: str,
    ):
        record = self.get_source_database_collection_relation_attribute(
            source,
            database,
            collection,
            relation,
            attribute,
        )
        return self.deregister(record)
                    