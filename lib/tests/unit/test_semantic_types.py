import pytest
from registry.enrichment.semantic_types import SemanticTypeInferencer


@pytest.fixture
def inferencer():
    return SemanticTypeInferencer()


# ---------------------------------------------------------------------------
# Numeric
# ---------------------------------------------------------------------------

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


def test_mixed_int_float(inferencer):
    result = inferencer.infer([1, 2.5, 3])
    assert result["semantic_type"] == "FLOAT"


def test_mixed_types_unknown(inferencer):
    result = inferencer.infer([1, "two", 3.0])
    assert result["semantic_type"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Null / empty
# ---------------------------------------------------------------------------

def test_empty_values(inferencer):
    result = inferencer.infer([])
    assert result["semantic_type"] == "UNKNOWN"
    assert result["confidence"] == 0.0


def test_all_null(inferencer):
    result = inferencer.infer([None, None])
    assert result["semantic_type"] == "UNKNOWN"


def test_nulls_skipped(inferencer):
    # Nulls should be ignored; non-null values determine the type
    result = inferencer.infer([None, 1, None, 2, 3])
    assert result["semantic_type"] == "INTEGER"


# ---------------------------------------------------------------------------
# String patterns
# ---------------------------------------------------------------------------

def test_email(inferencer):
    result = inferencer.infer(["alice@example.com", "bob@company.org", "carol@test.io"])
    assert result["semantic_type"] == "EMAIL"
    assert result["confidence"] >= 0.9


def test_url(inferencer):
    result = inferencer.infer(["https://example.com", "http://foo.bar/path"])
    assert result["semantic_type"] == "URL"
    assert result["confidence"] >= 0.9


def test_uuid(inferencer):
    uuids = [
        "550e8400-e29b-41d4-a716-446655440000",
        "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    ]
    result = inferencer.infer(uuids)
    assert result["semantic_type"] == "UUID"
    assert result["confidence"] >= 0.95


def test_date(inferencer):
    result = inferencer.infer(["2024-01-01", "2024-06-15", "2023-12-31"])
    assert result["semantic_type"] == "DATE"
    assert result["confidence"] >= 0.9


def test_datetime(inferencer):
    result = inferencer.infer([
        "2024-01-01T12:00:00Z",
        "2024-06-15T08:30:00+00:00",
        "2023-12-31T23:59:59Z",
    ])
    assert result["semantic_type"] == "DATETIME"


def test_datetime_wins_over_date(inferencer):
    # datetime pattern is more specific and checked first
    result = inferencer.infer(["2024-01-01T00:00:00Z"])
    assert result["semantic_type"] == "DATETIME"


def test_postal_code(inferencer):
    result = inferencer.infer(["90210", "10001", "94102", "60601"])
    assert result["semantic_type"] == "POSTAL_CODE"


def test_enum_category_low_cardinality(inferencer):
    # 3 distinct values across 20 rows → well below the 10% threshold
    values = (["active", "inactive", "pending"] * 7)[:20]
    result = inferencer.infer(values)
    assert result["semantic_type"] == "ENUM_CATEGORY"
    assert result["confidence"] >= 0.7


def test_free_text(inferencer):
    # Need enough distinct values to avoid the ENUM_CATEGORY cardinality gate,
    # AND average length > 50 chars to hit the free-text branch.
    base = "This is a long product description that clearly exceeds fifty characters "
    values = [base + str(i) for i in range(20)]
    result = inferencer.infer(values)
    assert result["semantic_type"] == "FREE_TEXT"


def test_string_generic(inferencer):
    # 20 distinct values well above the cardinality threshold — must stay STRING
    values = [f"user_{i}" for i in range(20)]
    result = inferencer.infer(values)
    assert result["semantic_type"] == "STRING"


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_examples_included(inferencer):
    result = inferencer.infer([10, 20, 30, 40, 50, 60])
    assert "examples" in result
    assert len(result["examples"]) <= 5


def test_result_has_required_keys(inferencer):
    result = inferencer.infer(["hello", "world"])
    assert {"semantic_type", "confidence", "rationale", "examples"} <= result.keys()


def test_confidence_in_range(inferencer):
    for values in [[1, 2, 3], ["a@b.com"], ["2024-01-01"], []]:
        result = inferencer.infer(values)
        assert 0.0 <= result["confidence"] <= 1.0
