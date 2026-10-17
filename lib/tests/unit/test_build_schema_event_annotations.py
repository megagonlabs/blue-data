"""#145 — build_schema_for_nl must surface entity-level process semantics (the
"event annotations": row_semantics=EVENT, event_time, constraints) under
include_metadata=True. Previously only attribute-level value_semantics/metadata
were included, so the process-reasoning demo had to inject event info by hand."""
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.source import DataSource
from blue_data.source.json.memory_json_source import MemoryJSONSource


class _StubSource(DataSource):
    def __init__(self, name):
        super().__init__(name, properties={"connection": {"protocol": "stub"}})


def _registry_with_event_entity():
    reg = DataRegistry(store=MemoryJSONSource())
    reg.register_source(_StubSource("mydb"))
    reg.register_source_database("mydb", "sales")
    reg.register_source_database_collection("mydb", "sales", "public")
    reg.register_source_database_collection_entity("mydb", "sales", "public", "trans")
    reg.register_source_database_collection_entity_attribute(
        "mydb", "sales", "public", "trans", "date",
        properties={"info": {"type": "DATE"}},
    )
    reg.set_source_database_collection_entity_property(
        "mydb", "sales", "public", "trans", "process_semantics",
        {"row_semantics": "EVENT", "event_time": "date",
         "constraints": {"requires_temporal_reasoning": True}},
    )
    return reg


def test_event_annotations_included_with_metadata():
    reg = _registry_with_event_entity()
    schema = reg.build_schema_for_nl("mydb", "sales", "public", include_metadata=True)
    trans = next(e for e in schema["entities"] if e["name"] == "trans")
    assert "process_semantics" in trans
    assert trans["process_semantics"]["row_semantics"] == "EVENT"
    assert trans["process_semantics"]["event_time"] == "date"


def test_event_annotations_omitted_without_metadata():
    reg = _registry_with_event_entity()
    schema = reg.build_schema_for_nl("mydb", "sales", "public", include_metadata=False)
    trans = next(e for e in schema["entities"] if e["name"] == "trans")
    assert "process_semantics" not in trans
    assert sorted(trans.keys()) == ["attributes", "name"]
