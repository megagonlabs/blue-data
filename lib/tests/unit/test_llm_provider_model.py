"""Regression tests for issue #101.

Three defects:
  1. the family base_spec default BLUE_DATA_LLM_MODEL=gpt-4o was exported by the CLI
     regardless of provider, so Anthropic calls used gpt-4o;
  2. the base_spec default provider was openai, contradicting the documented
     "blank = deterministic-only"; and
  3. a run where every LLM call failed still reported success.

These cover the model-resolution fix in build_enricher, the base_spec defaults,
and the failure accounting in MetaData.
"""
import types

import pytest

from blue_data.registry.enrichment.metadata import MetaData
from blue_data.utils.config.spec import base_spec


# ---------- base_spec defaults ----------

def test_base_spec_llm_defaults_match_docs():
    s = base_spec()
    # Blank provider == deterministic-only (docs/configuration.md).
    assert s["BLUE_DATA_LLM_PROVIDER"].default == ""
    # No hardcoded cross-provider model; resolved per provider in build_enricher.
    assert s["BLUE_DATA_LLM_MODEL"].default is None
    assert "BLUE_DATA_LLM_MODEL" not in [p.name for p in s.required()]


# ---------- build_enricher model resolution ----------

def _anthropic_recorder(seen):
    class _Messages:
        def create(self, **kw):
            seen.append(kw["model"])
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="ok")])

    class _Client:
        def __init__(self, **kw):
            self.messages = _Messages()

    return _Client


@pytest.mark.parametrize("model_env", [None, ""])
def test_anthropic_falls_through_to_claude_when_model_unset(monkeypatch, model_env):
    import anthropic
    seen = []
    monkeypatch.setattr(anthropic, "Anthropic", _anthropic_recorder(seen))
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder")
    monkeypatch.delenv("BLUE_DATA_REGISTRY_METADATA_LLM_MODEL", raising=False)
    if model_env is None:
        monkeypatch.delenv("BLUE_DATA_LLM_MODEL", raising=False)
    else:
        monkeypatch.setenv("BLUE_DATA_LLM_MODEL", model_env)

    from blue_data.config import build_enricher
    enricher = build_enricher()
    enricher._llm_fn("hi")

    assert seen == ["claude-opus-4-8"]


def test_anthropic_respects_explicit_model(monkeypatch):
    import anthropic
    seen = []
    monkeypatch.setattr(anthropic, "Anthropic", _anthropic_recorder(seen))
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder")
    monkeypatch.setenv("BLUE_DATA_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.delenv("BLUE_DATA_REGISTRY_METADATA_LLM_MODEL", raising=False)

    from blue_data.config import build_enricher
    build_enricher()._llm_fn("hi")

    assert seen == ["claude-sonnet-4-6"]


def test_openai_falls_through_to_gpt4o_when_model_empty(monkeypatch):
    import openai
    seen = []

    class _Completions:
        def create(self, **kw):
            seen.append(kw["model"])
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
            )

    class _Client:
        def __init__(self, **kw):
            self.chat = types.SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(openai, "OpenAI", _Client)
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setenv("BLUE_DATA_LLM_MODEL", "")  # exported empty must fall through
    monkeypatch.delenv("BLUE_DATA_REGISTRY_METADATA_LLM_MODEL", raising=False)

    from blue_data.config import build_enricher
    build_enricher()._llm_fn("hi")

    assert seen == ["gpt-4o"]


def test_blank_provider_is_deterministic_only(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "")
    from blue_data.config import build_enricher
    enricher = build_enricher()
    assert enricher._llm_fn is None


# ---------- MetaData failure accounting ----------

def test_metadata_counts_failures():
    def boom(prompt):
        raise RuntimeError("model not found")

    m = MetaData(llm_fn=boom)
    assert m._call_llm("p") is None
    assert m.llm_call_count == 1
    assert m.llm_success_count == 0


def test_metadata_counts_successes():
    m = MetaData(llm_fn=lambda p: "ok")
    assert m._call_llm("p") == "ok"
    assert m.llm_call_count == 1
    assert m.llm_success_count == 1


def test_metadata_no_llm_fn_records_no_calls():
    m = MetaData(llm_fn=None)
    assert m._call_llm("p") is None
    assert m.llm_call_count == 0
    assert m.llm_success_count == 0
