from registry.search.search_engine import SearchEngine
from registry.search.keyword_search import KeywordSearch


class RegistrySearch(SearchEngine):

    def __init__(
        self,
        registry,
        vector_source=None,
    ):
        self.registry = registry
        self.vector_source = vector_source

        self.keyword_engine = KeywordSearch()

    def keyword_search(
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

    def vector_search(self, *args, **kwargs):
        raise NotImplementedError

    def hybrid_search(self, *args, **kwargs):
        raise NotImplementedError

    def search_records_hierarchical(
        self,
        query,
        scope=None,
        page=0,
        page_size=10,
    ):
        return self.keyword_search(
            query=query,
            scope=scope,
            page=page,
            page_size=page_size,
        )