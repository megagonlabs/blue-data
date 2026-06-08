from __future__ import annotations

from typing import Any


class SemanticTypeInferencer:
    """Initial deterministic semantic type inferencer."""

    def infer(self, values: list[Any]) -> dict:
        non_null = [v for v in values if v is not None]

        if not non_null:
            return {
                "semantic_type": "UNKNOWN",
                "confidence": 0.0,
                "rationale": "No non-null values available.",
            }

        if all(isinstance(v, bool) for v in non_null):
            semantic_type = "BOOLEAN"
        elif all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
            semantic_type = "INTEGER"
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
            semantic_type = "NUMERIC_GENERAL"
        elif all(isinstance(v, str) for v in non_null):
            semantic_type = "STRING"
        else:
            semantic_type = "UNKNOWN"

        return {
            "semantic_type": semantic_type,
            "confidence": 0.7 if semantic_type != "UNKNOWN" else 0.3,
            "rationale": "Inferred from simple Python value types.",
            "examples": non_null[:5],
        }
