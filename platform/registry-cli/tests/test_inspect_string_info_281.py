"""#281: `source inspect` must not crash when an attribute's ``info`` is a bare
string. Doc-source and user-source store ``info`` as a string (the type /
description, which DataSchema.add_entity_attribute allows), and the old
``(props.get("info") or {}).get("type")`` raised ``'str' object has no
attribute 'get'`` at entity and attribute level.
"""
from registry_cli.main import _info_type, cli


# --- _info_type helper: tolerate string / dict / missing info ---

def test_info_type_accepts_string():
    assert _info_type({"info": "VARCHAR"}) == "VARCHAR"


def test_info_type_accepts_dict():
    assert _info_type({"info": {"type": "INTEGER"}}) == "INTEGER"


def test_info_type_missing_or_empty():
    assert _info_type({}) == ""
    assert _info_type({"info": None}) == ""
    assert _info_type({"info": {}}) == ""


# --- end-to-end: inspect an entity/attribute whose info is a string ---

def _add_string_info_attr(registry):
    registry.register_source_database_collection_entity_attribute(
        source="sales", database="prod", collection="public", entity="orders",
        attribute="note", properties={"info": "str"},  # doc/user-source shape
    )


def test_source_inspect_attribute_with_string_info(registry, runner):
    _add_string_info_attr(registry)
    result = runner.invoke(
        cli, ["source", "inspect", "sales", "prod", "public", "orders", "note"]
    )
    assert result.exit_code == 0, result.output
    assert "str" in result.output  # the type is shown, not a traceback


def test_source_inspect_entity_lists_string_info_attribute(registry, runner):
    _add_string_info_attr(registry)
    result = runner.invoke(
        cli, ["source", "inspect", "sales", "prod", "public", "orders"]
    )
    assert result.exit_code == 0, result.output
    assert "note" in result.output
