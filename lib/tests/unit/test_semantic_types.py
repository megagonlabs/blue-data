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


def test_float(inferencer):
    result = inferencer.infer([1.5, 2.0, 3.7])
    assert result["semantic_type"] == "FLOAT"


def test_string(inferencer):
    # 20 distinct values well above the cardinality threshold — must stay STRING
    values = [f"user_{i}" for i in range(20)]
    result = inferencer.infer(values)
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
