"""Regression guard for issue #214 (registry-cli README contradicted the code).

The README documented `blue-registry search ... --limit`, but the option is `--top-k`,
so the command errored with "No such option '--limit'". Keep the README's search option
in sync with the actual Click command.
"""
from pathlib import Path

from registry_cli.main import cli

_README = Path(__file__).resolve().parents[1] / "README.md"


def test_search_option_is_top_k_not_limit():
    search = cli.commands["search"]
    opts = {o for p in search.params for o in p.opts}
    # Code reality: the limit option is --top-k, there is no --limit.
    assert "--top-k" in opts
    assert "--limit" not in opts


def test_readme_search_uses_real_option():
    text = _README.read_text()
    assert "--top-k" in text
    assert "search \"orders\" --type entity --limit" not in text
    # No README code sample may reference the nonexistent --limit option.
    assert "--limit" not in text
