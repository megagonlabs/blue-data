"""Regression test for issue #108 (platform side).

get_registry() must wire a vector source + embedding function when an embedding
provider is configured, so platform search is real hybrid — not BM25-only. With no
provider it stays keyword-only. No network: the OpenAI client is stubbed.
"""
import types

import registry_cli.config as cfg


def _stub_openai(monkeypatch):
    import openai

    class _Embeddings:
        def create(self, model, input):
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[0.1, 0.2, 0.3, 0.4])])

    class _Client:
        def __init__(self, **kw):
            self.embeddings = _Embeddings()

    monkeypatch.setattr(openai, "OpenAI", _Client)


def test_registry_is_keyword_only_without_embedding_provider(monkeypatch):
    for var in ("BLUE_DATA_EMBEDDING_PROVIDER", "BLUE_DATA_SOURCES_CONFIG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "memory")
    cfg.reset_registry()
    try:
        reg = cfg.get_registry()
        assert reg.search_engine.vector_source is None
        assert reg.search_engine.embedding_fn is None
    finally:
        cfg.reset_registry()


def test_registry_wires_hybrid_when_embedding_provider_configured(monkeypatch):
    _stub_openai(monkeypatch)
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "memory")
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_DIM", "4")
    monkeypatch.delenv("BLUE_DATA_SOURCES_CONFIG", raising=False)
    cfg.reset_registry()
    try:
        reg = cfg.get_registry()
        assert reg.search_engine.vector_source is not None
        assert reg.search_engine.embedding_fn is not None
        assert reg._rebuild is True
    finally:
        cfg.reset_registry()
