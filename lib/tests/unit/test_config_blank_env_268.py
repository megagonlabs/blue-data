"""Regression tests for issue #268.

docs/configuration.md tells users to copy example.envrc and source it. That file
exported optional settings as empty strings, and config.py read them with
``os.environ.get(KEY, default)`` — so the empty string beat the documented default
(embedding model, vector source, scan prefix, …) and a blank
``BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL`` silently disabled hierarchical search.

config.py now treats an empty / whitespace-only value as unset. These tests pin that
every string setting falls through to its default when blank. No network: the OpenAI
client is stubbed. example.envrc itself no longer exports blanks (checked below).
"""
import os
import types

import pytest

from blue_data import config
from blue_data.config import (
    _getenv_str,
    build_embedding_fn,
    build_hybrid_config,
    build_store,
    build_vector_source,
)
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.file_vector_source import FileVectorSource


# ---------- the helper ----------

def test_getenv_str_treats_blank_and_whitespace_as_unset(monkeypatch):
    monkeypatch.setenv("BD_T268", "")
    assert _getenv_str("BD_T268", "fallback") == "fallback"
    monkeypatch.setenv("BD_T268", "   ")
    assert _getenv_str("BD_T268", "fallback") == "fallback"
    monkeypatch.delenv("BD_T268", raising=False)
    assert _getenv_str("BD_T268", "fallback") == "fallback"
    monkeypatch.setenv("BD_T268", "real")
    assert _getenv_str("BD_T268", "fallback") == "real"


# ---------- blank string settings fall through to the documented default ----------

def test_blank_vector_source_follows_the_store(monkeypatch, tmp_path):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "file")
    monkeypatch.setenv("BLUE_DATA_REGISTRY_FILE", str(tmp_path / "reg.json"))
    monkeypatch.setenv("BLUE_DATA_REGISTRY_VECTOR_SOURCE", "")  # blank export
    vs = build_vector_source(lambda t: [0.0])
    assert isinstance(vs, FileVectorSource)  # matched the store, not forced to memory


def test_blank_scan_prefix_uses_default():
    assert _getenv_str("BLUE_DATA_REGISTRY_VECTOR_SCAN_PREFIX", "blue_data_vec:") == "blue_data_vec:"


def test_blank_store_does_not_force_a_backend(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_STORE", "")
    assert isinstance(build_store(), MemoryJSONSource)  # library default; CLI layers its own


def test_blank_embedding_model_uses_default(monkeypatch):
    captured = {}

    class _Embeddings:
        def create(self, model, input):
            captured["model"] = model
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[0.0])])

    class _Client:
        def __init__(self, **kw):
            self.embeddings = _Embeddings()

    import openai
    monkeypatch.setattr(openai, "OpenAI", _Client)
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_MODEL", "")  # blank export

    build_embedding_fn()("hi")
    assert captured["model"] == "text-embedding-3-small"


def test_blank_provider_disables_embeddings(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_EMBEDDING_PROVIDER", "")
    assert build_embedding_fn() is None


# ---------- blank hierarchical keeps the default instead of becoming False ----------

def test_blank_hierarchical_keeps_default(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL", "")
    cfg = build_hybrid_config() or {}
    assert "hierarchical_enabled" not in cfg  # absent -> HybridSearch keeps its default (true)


def test_explicit_hierarchical_false_is_honored(monkeypatch):
    monkeypatch.setenv("BLUE_DATA_REGISTRY_SEARCH_HIERARCHICAL", "false")
    assert build_hybrid_config()["hierarchical_enabled"] is False


# ---------- example.envrc must not ship blank exports of optional settings ----------

def test_example_envrc_exports_no_blank_optional_settings():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))))
    envrc = os.path.join(root, "example.envrc")
    if not os.path.exists(envrc):
        pytest.skip("example.envrc not found from this checkout layout")
    with open(envrc) as f:
        offenders = [
            line.rstrip("\n") for line in f
            if line.strip().startswith("export ") and line.split("=", 1)[-1].split("#", 1)[0].strip() == ""
        ]
    assert not offenders, f"example.envrc exports blank optional settings: {offenders}"


def test_example_envrc_does_not_force_memory_store():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))))
    envrc = os.path.join(root, "example.envrc")
    if not os.path.exists(envrc):
        pytest.skip("example.envrc not found from this checkout layout")
    with open(envrc) as f:
        active = [l.strip() for l in f if l.strip().startswith("export BLUE_DATA_REGISTRY_STORE=")]
    assert not any(l.endswith("memory") or "=memory" in l for l in active), (
        f"example.envrc still force-exports the memory store: {active}"
    )


def test_example_envrc_does_not_pin_registry_file_to_cwd():
    # #300: an exported relative BLUE_DATA_REGISTRY_FILE pins the CLI registry to the
    # working directory, so `source add` in one dir is invisible from another.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))))
    envrc = os.path.join(root, "example.envrc")
    if not os.path.exists(envrc):
        pytest.skip("example.envrc not found from this checkout layout")
    with open(envrc) as f:
        active = [l.strip() for l in f if l.strip().startswith("export BLUE_DATA_REGISTRY_FILE=")]
    for line in active:
        value = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"\'')
        assert os.path.isabs(value), (
            f"example.envrc exports a non-absolute BLUE_DATA_REGISTRY_FILE: {line!r}"
        )
