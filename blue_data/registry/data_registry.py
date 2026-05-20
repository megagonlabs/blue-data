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