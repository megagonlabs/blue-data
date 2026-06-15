import math
import numpy as np
import pytest

from blue_data.core.utils.similarity_utils import (
    compute_bm25_score,
    normalize_bm25_scores,
    compute_vector_score,
)
from blue_data.registry.search.ranking import (
    combine_scores,
    normalize_weights,
    aggregate_value_scores,
)


# ---------------------------------------------------------------------------
# compute_bm25_score
# ---------------------------------------------------------------------------

def test_bm25_exact_match():
    score = compute_bm25_score("orders", "orders table")
    assert score > 0


def test_bm25_no_match():
    score = compute_bm25_score("revenue", "customer email address")
    assert score == 0.0


def test_bm25_empty_query():
    assert compute_bm25_score("", "some document text") == 0.0


def test_bm25_empty_doc():
    assert compute_bm25_score("orders", "") == 0.0


def test_bm25_schema_text_boosts_score():
    without = compute_bm25_score("orders", "table")
    with_schema = compute_bm25_score("orders", "table", schema_text="orders entity")
    assert with_schema > without


def test_bm25_multi_token_query():
    score = compute_bm25_score("customer email", "customer email address column")
    assert score > 0


def test_bm25_repeated_term_saturates():
    # BM25 saturates — doubling occurrences should not double the score
    once = compute_bm25_score("foo", "foo bar baz")
    twice = compute_bm25_score("foo", "foo foo bar baz")
    assert twice > once
    assert twice < once * 2


# ---------------------------------------------------------------------------
# normalize_bm25_scores
# ---------------------------------------------------------------------------

def test_normalize_minmax_range():
    scores = [0.0, 1.0, 2.0, 5.0]
    normed = normalize_bm25_scores(scores, method="minmax")
    assert normed[0] == pytest.approx(0.0)
    assert normed[-1] == pytest.approx(1.0)
    assert all(0.0 <= s <= 1.0 for s in normed)


def test_normalize_all_same():
    normed = normalize_bm25_scores([3.0, 3.0, 3.0], method="minmax")
    # all same and > 0 → all become 1.0
    assert all(s == 1.0 for s in normed)


def test_normalize_all_zero():
    normed = normalize_bm25_scores([0.0, 0.0], method="minmax")
    assert all(s == 0.0 for s in normed)


def test_normalize_empty():
    assert normalize_bm25_scores([]) == []


def test_normalize_log():
    scores = [0.0, 1.0, 4.0]
    normed = normalize_bm25_scores(scores, method="log")
    assert normed[-1] == pytest.approx(1.0)
    assert all(0.0 <= s <= 1.0 for s in normed)


def test_normalize_linear():
    scores = [0.0, 2.0, 4.0]
    normed = normalize_bm25_scores(scores, method="linear")
    assert normed[-1] == pytest.approx(1.0)
    assert normed[1] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# compute_vector_score
# ---------------------------------------------------------------------------

def test_vector_identical():
    v = [1.0, 0.0, 0.0]
    assert compute_vector_score(v, v) == pytest.approx(1.0)


def test_vector_orthogonal():
    # Cosine of orthogonal vectors is 0 → normalized to 0.5
    score = compute_vector_score([1.0, 0.0], [0.0, 1.0])
    assert score == pytest.approx(0.5)


def test_vector_opposite():
    # Cosine of opposite vectors is -1 → normalized to 0.0
    score = compute_vector_score([1.0, 0.0], [-1.0, 0.0])
    assert score == pytest.approx(0.0)


def test_vector_none():
    assert compute_vector_score(None, [1.0, 0.0]) == 0.0
    assert compute_vector_score([1.0, 0.0], None) == 0.0


def test_vector_zero_norm():
    assert compute_vector_score([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_vector_bytes_input():
    v = np.array([1.0, 0.0], dtype=np.float32)
    score = compute_vector_score(v.tobytes(), v.tobytes())
    assert score == pytest.approx(1.0)


def test_vector_no_normalize():
    v = [1.0, 0.0]
    score = compute_vector_score(v, v, normalize_score=False)
    assert score == pytest.approx(1.0)

    # cosine similarity of -1 is clipped to 0.0 by np.clip at the end
    opp = compute_vector_score(v, [-1.0, 0.0], normalize_score=False)
    assert opp == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# combine_scores
# ---------------------------------------------------------------------------

def test_combine_pure_bm25():
    score = combine_scores(1.0, 0.8, 0.0, 0.5)
    assert score == pytest.approx(0.8)


def test_combine_pure_vector():
    score = combine_scores(0.0, 0.8, 1.0, 0.6)
    assert score == pytest.approx(0.6)


def test_combine_equal_weights():
    score = combine_scores(0.5, 0.8, 0.5, 0.4)
    assert score == pytest.approx(0.6)


def test_combine_with_value():
    score = combine_scores(0.4, 0.5, 0.4, 0.5, value_weight=0.2, value_score=1.0)
    assert score == pytest.approx(0.4 * 0.5 + 0.4 * 0.5 + 0.2 * 1.0)


# ---------------------------------------------------------------------------
# normalize_weights
# ---------------------------------------------------------------------------

def test_normalize_weights_sums_to_one():
    w1, w2, w3 = normalize_weights(1.0, 2.0, 1.0)
    assert w1 + w2 + w3 == pytest.approx(1.0)


def test_normalize_weights_proportions():
    w1, w2, _ = normalize_weights(1.0, 1.0, 0.0)
    assert w1 == pytest.approx(0.5)
    assert w2 == pytest.approx(0.5)


def test_normalize_weights_all_zero():
    # All zero → returned as-is (no division)
    w1, w2, w3 = normalize_weights(0.0, 0.0, 0.0)
    assert (w1, w2, w3) == (0.0, 0.0, 0.0)


def test_normalize_weights_negative_raises():
    with pytest.raises(ValueError):
        normalize_weights(-1.0, 1.0)


# ---------------------------------------------------------------------------
# aggregate_value_scores
# ---------------------------------------------------------------------------

class _FakeRecord:
    def __init__(self, vs=0.0, avs=0.0):
        self.value_relevance_score = vs
        self.aggregated_value_relevance = avs


def _hierarchy(scores: list[float]) -> dict:
    return {
        str(i): {"record": _FakeRecord(vs=s)}
        for i, s in enumerate(scores)
    }


def test_aggregate_max():
    h = _hierarchy([0.3, 0.7, 0.5])
    score = aggregate_value_scores({"0", "1", "2"}, h, mode="max")
    assert score == pytest.approx(0.7)


def test_aggregate_topk():
    h = _hierarchy([0.9, 0.5, 0.1])
    score = aggregate_value_scores({"0", "1", "2"}, h, mode="topk", top_k=2)
    assert score == pytest.approx((0.9 + 0.5) / 2)


def test_aggregate_sum():
    h = _hierarchy([0.4, 0.3])
    score = aggregate_value_scores({"0", "1"}, h, mode="sum")
    assert score == pytest.approx(0.7)


def test_aggregate_decayed():
    h = _hierarchy([0.8, 0.4])
    score = aggregate_value_scores({"0", "1"}, h, mode="decayed", decay=0.5)
    assert score == pytest.approx(0.8 + 0.5 * 0.4)


def test_aggregate_empty_nodes():
    assert aggregate_value_scores(set(), {}, mode="max") == 0.0


def test_aggregate_missing_node_ids():
    h = _hierarchy([0.5])
    assert aggregate_value_scores({"999"}, h, mode="max") == 0.0
