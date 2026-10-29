"""Regression test for issue #210.

blue-registry is a multi-invocation tool, but BLUE_DATA_REGISTRY_STORE defaulted to
'memory', so each command started with an empty registry and the documented
`source add` → `source sync` workflow failed with SOURCE_NOT_FOUND. The CLI now
defaults to the file store at ~/.blue-registry/registry.json.
"""
from registry_cli.profile import cli_spec, profile_store, resolver_for


def test_cli_default_store_is_file():
    assert cli_spec()["BLUE_DATA_REGISTRY_STORE"].default == "file"


def test_resolver_defaults_store_to_file_under_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("BLUE_DATA_REGISTRY_STORE", "BLUE_DATA_REGISTRY_FILE", "BLUE_DATA_PROFILE"):
        monkeypatch.delenv(var, raising=False)

    home = str(tmp_path)
    profile_store(home).initialize()
    resolver = resolver_for(home)

    assert resolver.get("BLUE_DATA_REGISTRY_STORE") == "file"
    assert resolver.get("BLUE_DATA_REGISTRY_FILE").endswith("/.blue-registry/registry.json")
