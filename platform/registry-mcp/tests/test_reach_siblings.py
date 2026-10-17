"""#109 (XR-01) — reaching non-SQL sibling sources through the registry MCP server:
  * a query arriving as a JSON-object string is decoded to the dict dict-op
    sources (doc, kb, web) expect;
  * source-executing tools run off the event loop, so a sibling that calls its
    own ``asyncio.run`` (the user/kb pattern) no longer fails on a live loop.
"""
import asyncio
import json

import pytest

from registry_mcp import server as S


class _SiblingLikeRegistry:
    """execute_query runs its own event loop (user/kb pattern) and records the
    query value it received."""

    def __init__(self):
        self.received = "UNSET"

    def execute_query(self, source, query, database=None, collection=None):
        self.received = query

        async def _work():
            return [{"type": type(query).__name__}]

        return asyncio.run(_work())  # raises if executed on a live event loop


@pytest.fixture
def sibling_registry(monkeypatch):
    reg = _SiblingLikeRegistry()
    # server.py imported get_registry by name, so patch it in the server module.
    monkeypatch.setattr(S, "get_registry", lambda: reg)
    return reg


def test_execute_query_decodes_json_object_string(sibling_registry):
    out = json.loads(S.execute_query("docs", '{"op": "DOCUMENT.SEARCH", "query": "x"}'))
    assert sibling_registry.received == {"op": "DOCUMENT.SEARCH", "query": "x"}
    assert out == [{"type": "dict"}]


def test_execute_query_leaves_sql_string_unchanged(sibling_registry):
    json.loads(S.execute_query("shop", "select 1"))
    assert sibling_registry.received == "select 1"


def test_source_tool_runs_off_the_event_loop(sibling_registry):
    # Calling the sync tool from within a running loop: the wrapper must offload
    # to a worker thread, else the sibling's asyncio.run blows up and the tool
    # returns an {"error": ...} payload instead of rows.
    async def main():
        return S.execute_query("docs", "select 1")

    out = json.loads(asyncio.run(main()))
    assert out == [{"type": "str"}]
