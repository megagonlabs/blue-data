"""Pytest-importable conformance kit for the DataSource contract (design/14).

A source repo asserts it implements the contract by subclassing
``DataSourceConformance`` and providing a ``data_source`` fixture (and, to turn on
the behavioural checks, a ``sample_query``)::

    from blue_data.testing.conformance import DataSourceConformance

    class TestMySourceConformance(DataSourceConformance):
        @pytest.fixture
        def data_source(self):
            return MySource("t", properties={"connection": {...}})

        @pytest.fixture
        def sample_query(self):
            return ("SELECT 1 AS n", {"database": "t"})   # (query, kwargs); omit to skip behavioural checks

Structural checks (§2–§6) always run; behavioural checks (§1 list[dict], §3 commit)
run only when ``sample_query`` returns something other than ``None``.
"""
from __future__ import annotations

import inspect

import pytest

from blue_data.source.source import DataSource

# Keyword arguments DataRegistry.execute_query_nl passes to a source (design/14 §2).
_NL_QUERY_PARAMS = ("query", "database", "collection", "schema", "llm_fn", "optional_properties")


def _accepts(method, names) -> set:
    """Return the subset of *names* the callable does NOT accept (empty == all accepted)."""
    params = inspect.signature(method).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return set()
    return {n for n in names if n not in params}


def _split_sample(sample_query):
    """Normalise a sample_query fixture value to (query, kwargs)."""
    if isinstance(sample_query, tuple):
        query, kwargs = sample_query
        return query, dict(kwargs)
    return sample_query, {}


class DataSourceConformance:
    """Mixin of DataSource-contract tests. See module docstring and design/14."""

    # Subclasses may override to enable behavioural checks.
    @pytest.fixture
    def sample_query(self):
        return None

    # ---------------------------------------------------------------- structural

    def test_is_a_datasource(self, data_source):
        assert isinstance(data_source, DataSource)

    def test_execute_query_nl_accepts_registry_signature(self, data_source):
        """§2 — must accept query/database/collection/schema/llm_fn/optional_properties."""
        missing = _accepts(data_source.execute_query_nl, _NL_QUERY_PARAMS)
        assert not missing, (
            f"execute_query_nl does not accept {sorted(missing)} — "
            f"DataRegistry.execute_query_nl passes them as keywords"
        )

    def test_no_async_override_of_sync_base_methods(self, data_source):
        """§6 — a sync base method must not be overridden with async def."""
        cls = type(data_source)
        violations = []
        for name, base_fn in inspect.getmembers(DataSource, predicate=inspect.isfunction):
            if name.startswith("__") or inspect.iscoroutinefunction(base_fn):
                continue
            override = getattr(cls, name, None)
            if inspect.iscoroutinefunction(override):
                violations.append(name)
        assert not violations, f"async overrides of sync base methods: {sorted(violations)}"

    def test_reconstructible_from_properties(self, data_source):
        """§4 — rebuildable from (name, properties) alone, via its _class path."""
        cls = type(data_source)
        path = f"{cls.__module__}.{cls.__qualname__}"
        rebuilt = DataSource.instantiate(path, data_source.name, properties=data_source.properties)
        assert isinstance(rebuilt, cls)

    def test_reserved_metadata_property_tolerated(self, data_source):
        """§3 — a reserved `metadata` property must not break (re)construction."""
        cls = type(data_source)
        path = f"{cls.__module__}.{cls.__qualname__}"
        props = dict(data_source.properties)
        props["metadata"] = {"note": "conformance"}
        rebuilt = DataSource.instantiate(path, data_source.name, properties=props)
        assert isinstance(rebuilt, cls)

    # ---------------------------------------------------------------- behavioural

    def test_execute_query_returns_list_of_dicts(self, data_source, sample_query):
        """§1 — execute_query returns a list of dict rows."""
        if sample_query is None:
            pytest.skip("no sample_query fixture; behavioural check skipped")
        query, kwargs = _split_sample(sample_query)
        out = data_source.execute_query(query, **kwargs)
        assert isinstance(out, list), f"execute_query returned {type(out).__name__}, expected list"
        assert all(isinstance(r, dict) for r in out), "every row must be a dict"

    def test_execute_query_tolerates_commit_optional_property(self, data_source, sample_query):
        """§3 — a read with optional_properties={'commit': False} must be accepted."""
        if sample_query is None:
            pytest.skip("no sample_query fixture; behavioural check skipped")
        query, kwargs = _split_sample(sample_query)
        kwargs["optional_properties"] = {**kwargs.get("optional_properties", {}), "commit": False}
        out = data_source.execute_query(query, **kwargs)
        assert isinstance(out, list)
