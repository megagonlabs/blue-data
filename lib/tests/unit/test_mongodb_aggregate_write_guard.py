"""Regression tests for issue #248.

MongoDBSource declared AGGREGATE a read, so a pipeline with a $out or $merge stage
wrote (or replaced) a collection without commit. AGGREGATE is now classified on its
pipeline: a $out/$merge stage at any depth needs commit, in the registry guard, in
the source's own AGGREGATE branch and in the NL tool loop. Server-free: MongoClient
is mocked, and a pipeline reaching the driver shows up as an aggregate() call.
"""
import json
from unittest.mock import patch

import pytest

pytest.importorskip("pymongo")
from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.mongodb import mongodb_json_source as mod
from blue_data.source.json.mongodb.mongodb_json_source import MongoDBSource

WRITING_PIPELINES = {
    "out": [{"$match": {}}, {"$out": "copy"}],
    "merge": [{"$match": {}}, {"$merge": {"into": "merged"}}],
    "facet": [{"$facet": {"a": [{"$match": {}}, {"$out": "copy"}]}}],
    "lookup": [{"$lookup": {"from": "other", "as": "o",
                            "pipeline": [{"$merge": {"into": "merged"}}]}}],
    "union_with": [{"$unionWith": {"coll": "other", "pipeline": [{"$out": "copy"}]}}],
}
READ_PIPELINE = [{"$group": {"_id": "$name", "n": {"$sum": 1}}}]


@pytest.fixture
def mongo():
    with patch.object(mod, "MongoClient"):
        src = MongoDBSource("mongo", properties={"connection": {"host": "h", "port": 1}})
        src.connection["db"]["people"].aggregate.return_value = []
        yield src


def _aggregate_calls(src):
    return src.connection["db"]["people"].aggregate.call_args_list


def _registry(src):
    reg = DataRegistry()
    reg.register_source(src)
    return reg


@pytest.mark.parametrize("pipeline", WRITING_PIPELINES.values(), ids=WRITING_PIPELINES.keys())
@pytest.mark.parametrize("encode", [False, True])
def test_registry_refuses_writing_aggregate_without_commit(mongo, pipeline, encode):
    query = {"op": "AGGREGATE", "pipeline": pipeline}
    with pytest.raises(ValueError, match="commit"):
        _registry(mongo).execute_query("mongo", json.dumps(query) if encode else query,
                                       database="db", collection="people")
    assert not _aggregate_calls(mongo)


@pytest.mark.parametrize("pipeline", WRITING_PIPELINES.values(), ids=WRITING_PIPELINES.keys())
def test_writing_aggregate_runs_with_commit(mongo, pipeline):
    _registry(mongo).execute_query("mongo", {"op": "AGGREGATE", "pipeline": pipeline},
                                   database="db", collection="people",
                                   optional_properties={"commit": True})
    assert _aggregate_calls(mongo)[0].args[0] == pipeline


def test_reading_aggregate_runs_without_commit(mongo):
    _registry(mongo).execute_query("mongo", {"op": "aggregate", "pipeline": READ_PIPELINE},
                                   database="db", collection="people")
    assert _aggregate_calls(mongo)[0].args[0] == READ_PIPELINE


def test_source_execute_query_refuses_writing_aggregate_without_commit(mongo):
    """Library callers that skip the registry are guarded by the source itself."""
    with pytest.raises(ValueError, match="commit"):
        mongo.execute_query({"op": "AGGREGATE", "pipeline": WRITING_PIPELINES["out"]},
                            database="db", collection="people")
    assert not _aggregate_calls(mongo)


@pytest.mark.parametrize("pipeline", WRITING_PIPELINES.values(), ids=WRITING_PIPELINES.keys())
def test_writing_aggregate_is_a_write_native_query(mongo, pipeline):
    assert mongo._query_requires_commit({"op": "AGGREGATE", "pipeline": pipeline})
    assert mongo._is_write_native_query({"op": "AGGREGATE", "pipeline": pipeline})
    assert not mongo._is_write_native_query({"op": "AGGREGATE", "pipeline": READ_PIPELINE})


def _tool_llm(pipeline):
    """An LLM that calls the aggregate tool once with *pipeline*, then answers."""
    turns = iter([
        {"stop_reason": "tool_use", "content": [{
            "type": "tool_use", "id": "t1", "name": "aggregate",
            "input": {"database": "db", "collection": "people", "pipeline": pipeline},
        }]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]},
    ])
    messages_seen = []

    def llm_fn(messages, tools, system=None):
        messages_seen.append(list(messages))
        return next(turns)

    return llm_fn, messages_seen


def test_nl_tool_loop_refuses_model_written_out_stage(mongo):
    llm_fn, seen = _tool_llm(WRITING_PIPELINES["out"])
    mongo.execute_query_nl_tools("copy everyone", database="db", collection="people",
                                 llm_fn=llm_fn, optional_properties={"commit": True})
    assert not _aggregate_calls(mongo)
    assert "commit" in seen[-1][-1]["content"][0]["content"]


def test_nl_tool_loop_runs_out_stage_when_writes_opted_in(mongo):
    llm_fn, _ = _tool_llm(WRITING_PIPELINES["out"])
    mongo.execute_query_nl_tools("copy everyone", database="db", collection="people",
                                 llm_fn=llm_fn, read_only=False,
                                 optional_properties={"commit": True})
    assert _aggregate_calls(mongo)[0].args[0] == WRITING_PIPELINES["out"]
