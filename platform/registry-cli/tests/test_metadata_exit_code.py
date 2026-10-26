"""CLI exit-code behaviour for `source metadata` — issue #101.

A run where every LLM call failed must exit non-zero instead of printing success.
"""
from blue_data.registry.enrichment.metadata import MetaData

from registry_cli.main import cli


def test_all_llm_calls_failing_exits_nonzero(registry, runner):
    def boom(prompt):
        raise RuntimeError("model not found: gpt-4o")

    registry.metadata_enricher = MetaData(llm_fn=boom)

    result = runner.invoke(cli, ["source", "metadata", "sales"])

    assert result.exit_code != 0
    assert "ENRICHMENT_FAILED" in result.output


def test_successful_enrichment_exits_zero(registry, runner):
    registry.metadata_enricher = MetaData(llm_fn=lambda prompt: "{}")

    result = runner.invoke(cli, ["source", "metadata", "sales"])

    assert result.exit_code == 0
    assert "complete" in result.output


def test_deterministic_only_exits_zero(registry, runner):
    registry.metadata_enricher = MetaData(llm_fn=None)

    result = runner.invoke(cli, ["source", "metadata", "sales"])

    assert result.exit_code == 0
