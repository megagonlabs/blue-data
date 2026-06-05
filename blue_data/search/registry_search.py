from blue_data.search.search_engine import SearchEngine
from blue_data.search.keyword_search import KeywordSearch


class RegistrySearch(SearchEngine):

    def __init__(
        self,
        registry,
        vector_source=None,
    ):
        self.registry = registry
        self.vector_source = vector_source

        self.keyword_engine = KeywordSearch()

    def search_records(
        self,
        query,
        scope=None,
        record_type=None,
        page=0,
        page_size=10,
    ):
        records = self.registry.list_records()

        return self.keyword_engine.search(
            records=records,
            query=query,
            scope=scope,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

    def search_records_hierarchical(
        self,
        query,
        scope=None,
        page=0,
        page_size=10,
    ):
        return self.search_records(
            query=query,
            scope=scope,
            page=page,
            page_size=page_size,
        )