from __future__ import annotations

import datetime as _dt
import math as _math
from decimal import Decimal as _Decimal
from typing import Any

from jsonpath_ng import parse as _parse


def json_safe(obj: Any) -> Any:
    """Recursively coerce *obj* into JSON-serializable primitives.

    Driver values that reach the registry (e.g. source stats and sample values)
    are not always JSON-native: Postgres/MySQL return ``date``/``datetime`` and
    ``Decimal``, MongoDB returns ``ObjectId`` and ``bytes``. The registry persists
    records as JSON (file store via ``json.dump``, Redis via RedisJSON), so any
    such value crashes ``collect_source_stats`` / ``enrich`` / ``metadata`` with
    "Object of type X is not JSON serializable" (#264). Normalise once, at the
    registry write boundary, so every store — and every LLM prompt built from the
    stored stats — sees only primitives.

    - ``date`` / ``datetime`` / ``time`` → ISO-8601 string
    - non-finite ``float`` / ``Decimal`` (``NaN``, ``±Infinity``) → ``None``
    - ``Decimal`` → ``float``
    - ``bytes`` / ``bytearray`` / ``memoryview`` → UTF-8 text, else hex
    - ``set`` / ``tuple`` → ``list`` (recursed)
    - ``dict`` / ``list`` → recursed
    - any remaining exotic type (``ObjectId``, ``UUID``, …) → ``str``.

    ``NaN``/``Infinity`` map to ``None`` because, although Python's ``json.dump``
    emits them, they are not valid JSON: RedisJSON rejects them, and a strict parser
    (and FastAPI's response encoder) raise on them — so a single sampled non-finite
    value broke the Redis store and the REST read of a file store (#294).
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if _math.isfinite(obj) else None
    if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
        return obj.isoformat()
    if isinstance(obj, _Decimal):
        if obj.is_nan() or obj.is_infinite():
            return None
        return float(obj)
    if isinstance(obj, (bytes, bytearray, memoryview)):
        try:
            return bytes(obj).decode("utf-8")
        except UnicodeDecodeError:
            return bytes(obj).hex()
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    return str(obj)  # ObjectId, UUID, and any other non-JSON type


def _normalize(path: str) -> str:
    """Convert dot-notation path to JSONPath expression (e.g. 'user.age' → '$.user.age')."""
    if path.startswith("$"):
        return path
    return f"$.{path}"


def json_query(data: Any, path: str, single: bool = False) -> Any:
    """Read values from data using a JSONPath or dot-notation path.

    Examples:
        json_query(data, "user.age")        → value at data["user"]["age"]
        json_query(data, "$[*].name")       → list of all names
        json_query(data, "users", single=True) → first match only
    """
    if data is None:
        return None if single else []

    expr = _parse(_normalize(path))
    matches = [m.value for m in expr.find(data)]

    if single:
        return matches[0] if matches else None
    return matches


def json_query_set(data: dict, path: str, value: Any) -> None:
    """Set a value at a dot-notation path, creating intermediate dicts as needed.

    Example:
        json_query_set(data, "user.age", 30)
        # data["user"]["age"] == 30, creating data["user"] = {} if absent
    """
    parts = _path_parts(path)
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def json_query_get(data: Any, path: str) -> Any:
    """Get a value at a dot-notation path. Returns None if path does not exist.

    Handles both flat keys (e.g. 'users/alice') and nested paths (e.g. 'user.age').
    Unlike json_query, this does not use jsonpath_ng so any key format is safe.
    """
    parts = _path_parts(path)
    val = data
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


def json_query_update(data: dict, path: str, value: Any) -> None:
    """Update an existing value at a dot-notation path. No-op if path does not exist.

    Example:
        json_query_update(data, "user.age", 31)
        # updates only if data["user"]["age"] already exists
    """
    parts = _path_parts(path)
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict) and parts[-1] in current:
        current[parts[-1]] = value


def json_query_delete(data: dict, path: str) -> None:
    """Delete a value at a dot-notation path. No-op if path does not exist.

    Example:
        json_query_delete(data, "user.age")
        # removes data["user"]["age"]
    """
    parts = _path_parts(path)
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _path_parts(path: str) -> list[str]:
    """Convert 'user.age' or '$.user.age' to ['user', 'age']."""
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    return path.split(".")
