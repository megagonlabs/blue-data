from __future__ import annotations

from blue_data.core.source import DataSource


class DataRegistry:
    """In-memory registry for data sources."""

    def __init__(self):
        self.sources: dict[str, DataSource] = {}

    def register_source(self, source: DataSource) -> None:
        self.sources[source.name] = source

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