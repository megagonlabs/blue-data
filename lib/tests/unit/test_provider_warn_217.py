"""Regression tests for issue #217.

A configured LLM or embedding provider was silently dropped when its SDK was not
installed (``except ImportError: pass``) or its API key was unset (fell through to
a null function). Operators got keyword-only search / no enrichment with no signal.

build_enricher and build_embedding_fn must now emit a WARNING naming the env var
and the missing package/key. Missing-SDK is simulated with ``sys.modules[name] =
None``, which makes ``import name`` raise ImportError without uninstalling anything.
"""
import logging
import sys


# ---------- build_enricher ----------

def test_enricher_warns_when_anthropic_key_missing(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from blue_data.config import build_enricher
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        enricher = build_enricher()

    assert enricher._llm_fn is None
    assert "ANTHROPIC_API_KEY" in caplog.text
    assert "anthropic" in caplog.text.lower()


def test_enricher_warns_when_openai_sdk_missing(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setitem(sys.modules, "openai", None)  # import openai -> ImportError

    from blue_data.config import build_enricher
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        enricher = build_enricher()

    assert enricher._llm_fn is None
    assert "openai" in caplog.text
    assert "not installed" in caplog.text


def test_enricher_warns_on_unknown_provider(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_LLM_PROVIDER", "cohere")

    from blue_data.config import build_enricher
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        enricher = build_enricher()

    assert enricher._llm_fn is None
    assert "cohere" in caplog.text.lower()


def test_enricher_silent_when_no_provider(monkeypatch, caplog):
    monkeypatch.delenv("BLUE_DATA_LLM_PROVIDER", raising=False)

    from blue_data.config import build_enricher
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        enricher = build_enricher()

    assert enricher._llm_fn is None
    assert caplog.text == ""


# ---------- build_embedding_fn ----------

def test_embedding_warns_when_key_missing(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from blue_data.config import build_embedding_fn
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        fn = build_embedding_fn()

    assert fn is None
    assert "OPENAI_API_KEY" in caplog.text


def test_embedding_warns_when_sdk_missing(monkeypatch, caplog):
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setitem(sys.modules, "openai", None)

    from blue_data.config import build_embedding_fn
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        fn = build_embedding_fn()

    assert fn is None
    assert "openai" in caplog.text
    assert "not installed" in caplog.text


def test_embedding_silent_when_no_provider(monkeypatch, caplog):
    monkeypatch.delenv("BLUE_DATA_EMBEDDING_PROVIDER", raising=False)

    from blue_data.config import build_embedding_fn
    with caplog.at_level(logging.WARNING, logger="blue_data.config"):
        fn = build_embedding_fn()

    assert fn is None
    assert caplog.text == ""
