from __future__ import annotations


def deep_merge(base: dict, update: dict) -> dict:
    """
    Recursively merge nested dictionaries.

    Values from `update` override values in `base`.
    Nested dictionaries are merged recursively.
    """

    result = dict(base)

    for key, value in update.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result