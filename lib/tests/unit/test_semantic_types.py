import pytest
from registry.enrichment.semantic_types import SemanticTypeInferencer


@pytest.fixture
def inferencer():
    return SemanticTypeInferencer()


def test_integer(inferencer):
    result = inferencer.infer([1, 2, 3])
    assert result["semantic_type"] == "INTEGER"
    assert result["confidence"] > 0


def test_boolean(inferencer):
    result = inferencer.infer([True, False, True])
    assert result["semantic_type"] == "BOOLEAN"


def test_numeric_general(inferencer):
    result = inferencer.infer([1.5, 2.0, 3.7])
    assert result["semantic_type"] == "NUMERIC_GENERAL"


def test_string(inferencer):
    result = inferencer.infer(["alice", "bob", "carol"])
    assert result["semantic_type"] == "STRING"


def test_empty_values(inferencer):
    result = inferencer.infer([])
    assert result["semantic_type"] == "UNKNOWN"
    assert result["confidence"] == 0.0


def test_all_null(inferencer):
    result = inferencer.infer([None, None])
    assert result["semantic_type"] == "UNKNOWN"


def test_examples_included(inferencer):
    result = inferencer.infer([10, 20, 30, 40, 50, 60])
    assert "examples" in result
    assert len(result["examples"]) <= 5
