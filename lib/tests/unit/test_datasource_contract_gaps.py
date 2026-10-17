"""#110 (XR-02) — blue-data's concrete contract gaps:
  * the base NL `get_sample` tool passed `row_sample_size` to `fetch_entity_stats`
    implementations that don't accept it (TypeError);
  * the registry's granular sync/stats methods called source methods no class
    defined (AttributeError).
Both are fixed on the base DataSource so every source answers them."""
import pytest

from blue_data.source.source import DataSource
from blue_data.registry.data_registry import DataRegistry


class _NoSampleStats(DataSource):
    """A source whose fetch_entity_stats does NOT accept row_sample_size."""

    def __init__(self):
        super().__init__("nosample", properties={"connection": {"protocol": "stub"}})
        self.received = None

    def fetch_entity_stats(self, database, collection, entity):  # no row_sample_size
        self.received = (database, collection, entity)
        return {"entity": entity}


class _SampleStats(DataSource):
    """A source whose fetch_entity_stats DOES accept row_sample_size."""

    def __init__(self):
        super().__init__("sample", properties={"connection": {"protocol": "stub"}})
        self.sample = None

    def fetch_entity_stats(self, database, collection, entity, row_sample_size=10):
        self.sample = row_sample_size
        return {"entity": entity, "row_sample_size": row_sample_size}


# ---------- get_sample dispatch ----------

def test_get_sample_omits_row_sample_size_when_unsupported():
    src = _NoSampleStats()
    out = src.execute_nl_tool("get_sample", {"database": "d", "collection": "c", "entity": "E"})
    assert out == {"entity": "E"}
    assert src.received == ("d", "c", "E")


def test_get_sample_passes_row_sample_size_when_supported():
    src = _SampleStats()
    src.execute_nl_tool("get_sample", {"database": "d", "collection": "c", "entity": "E", "sample_size": 7})
    assert src.sample == 7


# ---------- phantom registry calls now have base defaults ----------

def test_base_datasource_defines_the_formerly_phantom_methods():
    src = DataSource("base", properties={"connection": {"protocol": "stub"}})
    assert src.fetch_database_collection_entity_metadata("d", "c", "E") == {}
    assert src.fetch_database_collection_entity_attributes("d", "c", "E") == {}
    assert src.fetch_database_collection_relation_metadata("d", "c", "R") == {}
    assert src.fetch_database_collection_relation_attributes("d", "c", "R") == {}
    assert src.fetch_relation_stats("d", "c", "R") is None


def test_entity_attributes_default_derives_from_bulk():
    class _Bulk(DataSource):
        def __init__(self):
            super().__init__("bulk", properties={"connection": {"protocol": "stub"}})

        def fetch_database_collection_entities(self, database, collection):
            return {"orders": {"contents": {"attributes": {"id": {"type": "INTEGER"}}}}}

    assert _Bulk().fetch_database_collection_entity_attributes("d", "c", "orders") == {"id": {"type": "INTEGER"}}


def test_registry_granular_sync_and_stats_do_not_raise():
    class _Src(DataSource):
        def __init__(self):
            super().__init__("s", properties={"connection": {"protocol": "stub"}})

        def fetch_database_collection_entities(self, database, collection):
            return {"Company": {"contents": {"attributes": {}}}}

    reg = DataRegistry()
    src = _Src()
    reg.register_source(src)
    # previously raised AttributeError on fetch_*_metadata / fetch_relation_stats
    reg.sync_source_database_collection_entity("s", "main", "default", "Company", source_obj=src)
    reg.collect_relation_stats("s", "main", "default", "works_at")
