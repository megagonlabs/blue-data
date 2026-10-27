"""Regression tests for issue #108 (blue_data.config side).

The platforms build DataRegistry without a vector source / embedding function, so
hybrid search was BM25-only everywhere. blue_data.config now exposes env-driven
build_embedding_fn / build_vector_source; wiring them enables hybrid search when an
embedding provider is configured, and leaves the registry keyword-only otherwise.
No network: the OpenAI client is stubbed.
"""
import types

from blue_data.config import build_embedding_fn, build_vector_source
from blue_data.source.vector.memory_vector_source import MemoryVectorSource


def _stub_openai(monkeypatch):
    import openai

    class _Embeddings:
        def create(self, model, input):
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    class _Client:
        def __init__(self, **kw):
            self.embeddings = _Embeddings()

    monkeypatch.setattr(openai, "OpenAI", _Client)


def test_no_embedding_provider_returns_none(monkeypatch):
    monkeypatch.delenv("BLUE_DATA_EMBEDDING_PROVIDER", raising=False)
    assert build_embedding_fn() is None
    assert build_vector_source(None) is None


def test_openai_provider_builds_embedding_fn(monkeypatch):
    _stub_openai(monkeypatch)
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")

    fn = build_embedding_fn()
    assert fn is not None
    assert fn("hello") == [0.1, 0.2, 0.3]


def test_vector_source_defaults_to_memory_when_embeddings_available(monkeypatch):
    fn = lambda text: [0.1, 0.2, 0.3]
    monkeypatch.delenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", raising=False)
    assert isinstance(build_vector_source(fn), MemoryVectorSource)


def test_vector_source_none_without_embeddings():
    # Vector search needs embeddings; no dead vector source without them.
    assert build_vector_source(None) is None
