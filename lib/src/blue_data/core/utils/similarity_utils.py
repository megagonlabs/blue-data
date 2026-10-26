from __future__ import annotations

import math
import re
from typing import Any

import numpy as np


# Split camelCase / PascalCase and acronym boundaries: shipCountry -> ship Country,
# HTTPServer -> HTTP Server.
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")


def tokenize_text(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics (``_``, punctuation, whitespace) and
    camelCase boundaries, and drop empties. So ``order_date`` and ``ShipCountry``
    tokenize to the same words a natural-language query produces, and trailing
    punctuation (``freight?``) is ignored. #103"""
    if not text:
        return []
    spaced = _CAMEL_BOUNDARY_RE.sub(" ", str(text))
    return [t.lower() for t in _NON_ALNUM_RE.split(spaced) if t]


def compute_bm25_score(
    query: str,
    doc_text: str,
    schema_text: str | None = None,
) -> float:
    """BM25 Okapi TF score between a query and a single document.

    Without a corpus, IDF is omitted and only the TF saturation term is used.
    schema_text is appended to the document when provided (used for collections).
    Tokenization splits snake_case / camelCase and strips punctuation (#103).
    """
    k1 = 1.5
    b = 0.75

    query_tokens = tokenize_text(query) if query else []
    doc_tokens = tokenize_text(doc_text)
    if schema_text:
        doc_tokens = doc_tokens + tokenize_text(schema_text)

    if not doc_tokens or not query_tokens:
        return 0.0

    doc_length = len(doc_tokens)
    avg_dl = doc_length  # single document — length norm cancels

    tf: dict[str, int] = {}
    for token in doc_tokens:
        tf[token] = tf.get(token, 0) + 1

    score = 0.0
    for term in set(query_tokens):
        if term in tf:
            freq = tf[term]
            score += (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_length / avg_dl))

    return score


def normalize_bm25_scores(
    scores: list[float],
    method: str = "minmax",
) -> list[float]:
    """Normalize a list of BM25 scores to [0, 1].

    Supported methods: 'minmax', 'log', 'linear'.
    """
    if not scores:
        return []

    if method == "minmax":
        min_s = min(scores)
        max_s = max(scores)
        if max_s == min_s:
            return [1.0 if s > 0 else 0.0 for s in scores]
        return [(s - min_s) / (max_s - min_s) for s in scores]

    if method == "log":
        log_scores = [math.log1p(max(0.0, s)) for s in scores]
        max_s = max(log_scores) if log_scores else 0.0
        if max_s == 0.0:
            return [0.0] * len(scores)
        return [s / max_s for s in log_scores]

    if method == "linear":
        max_s = max(scores) if scores else 0.0
        if max_s == 0.0:
            return [0.0] * len(scores)
        return [s / max_s for s in scores]

    return list(scores)


def compute_vector_score(
    query_vector: Any,
    doc_vector: Any,
    normalize_score: bool = True,
) -> float:
    """Cosine similarity between two vectors.

    Accepts numpy arrays, lists of floats, or raw bytes (float32 little-endian).
    Returns a value in [0, 1] when normalize_score=True (maps [-1,1] → [0,1]).
    """
    if query_vector is None or doc_vector is None:
        return 0.0

    if isinstance(query_vector, (bytes, bytearray)):
        query_vector = np.frombuffer(query_vector, dtype=np.float32)
    if isinstance(doc_vector, (bytes, bytearray)):
        doc_vector = np.frombuffer(doc_vector, dtype=np.float32)

    q = np.asarray(query_vector, dtype=np.float32).ravel()
    d = np.asarray(doc_vector, dtype=np.float32).ravel()

    q_norm = float(np.linalg.norm(q))
    d_norm = float(np.linalg.norm(d))

    if q_norm == 0.0 or d_norm == 0.0:
        return 0.0

    similarity = float(np.dot(q, d) / (q_norm * d_norm))

    if normalize_score:
        similarity = (similarity + 1.0) / 2.0

    return float(np.clip(similarity, 0.0, 1.0))
