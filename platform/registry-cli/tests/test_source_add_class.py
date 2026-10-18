"""#109 (XR-01, deferred item) — `blue-registry source add --class` registers any
DataSource subclass by its fully-qualified path, and `source add` requires either
--type or --class."""
import json

import pytest
from click.testing import CliRunner

from registry_cli.main import cli


@pytest.fixture
def env(tmp_path):
    return {
        "HOME": str(tmp_path / "home"),
        "BLUE_DATA_REGISTRY_STORE": "file",
        "BLUE_DATA_REGISTRY_FILE": str(tmp_path / "registry.json"),
    }


def test_source_add_class_registers_and_lists(env, tmp_path):
    runner = CliRunner()
    r = runner.invoke(cli, [
        "source", "add", "shop", "--class",
        "blue_data.source.sql.sqlite.sqlite_sql_source.SQLiteDBSource",
        "--properties", json.dumps({"connection": {"database_directory": str(tmp_path / "sql")}}),
    ], env=env)
    assert r.exit_code == 0, r.output
    assert "Registered source 'shop'" in r.output

    listed = runner.invoke(cli, ["source", "list"], env=env)
    assert listed.exit_code == 0
    assert "shop" in listed.output


def test_source_add_requires_type_or_class(env):
    r = CliRunner().invoke(cli, ["source", "add", "nope"], env=env)
    assert r.exit_code != 0
    assert "either --type" in r.output
