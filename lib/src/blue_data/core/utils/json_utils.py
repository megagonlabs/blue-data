from __future__ import annotations

import re
from typing import Any


def json_query(data: Any, path: str, single: bool = False) -> Any:
    """Minimal JSONPath-like query supporting the patterns used in blue-data.

    Supported patterns:
        $[*].key            — extract key from every item in a list
        $[*].key1.key2      — nested extraction from list items
        $[n].key            — extract key from item at index n
        $.key               — extract key from a dict
    """
    if data is None:
        return None if single else []

    # $[*].key or $[*].key1.key2
    if re.match(r'^\$\[\*\]\.', path):
        keys = path[5:].split(".")
        if not isinstance(data, list):
            return None if single else []
        results = []
        for item in data:
            val = item
            for key in keys:
                val = val.get(key) if isinstance(val, dict) else None
                if val is None:
                    break
            if val is not None:
                results.append(val)
        return results[0] if (single and results) else (None if single else results)

    # $[n].key
    index_match = re.match(r'^\$\[(\d+)\]\.(.+)$', path)
    if index_match:
        idx = int(index_match.group(1))
        keys = index_match.group(2).split(".")
        if not isinstance(data, list) or idx >= len(data):
            return None if single else []
        val = data[idx]
        for key in keys:
            val = val.get(key) if isinstance(val, dict) else None
            if val is None:
                break
        return val if single else ([val] if val is not None else [])

    # $.key or $.key1.key2
    simple_match = re.match(r'^\$\.(.+)$', path)
    if simple_match:
        keys = simple_match.group(1).split(".")
        val = data
        for key in keys:
            val = val.get(key) if isinstance(val, dict) else None
            if val is None:
                break
        return val if single else ([val] if val is not None else [])

    return None if single else []
