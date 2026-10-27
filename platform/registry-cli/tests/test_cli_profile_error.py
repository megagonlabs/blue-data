"""CLI behaviour for issue #88: a missing/misspelled profile is a configuration
error, not a silent fall-through to env + defaults."""
from registry_cli.main import cli


def test_misspelled_profile_is_a_config_error(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_HOME", str(tmp_path))

    result = runner.invoke(cli, ["--profile", "ghost", "source", "list"])

    assert result.exit_code != 0
    assert "CONFIG_ERROR" in result.output


def test_fresh_install_default_profile_works(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_HOME", str(tmp_path))

    result = runner.invoke(cli, ["source", "list"])

    assert result.exit_code == 0
