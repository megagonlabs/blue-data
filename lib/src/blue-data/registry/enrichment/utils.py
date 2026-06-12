from __future__ import annotations

import json
import re


def safe_json_parse(text: str | None) -> dict | list | None:
    """Parse JSON from an LLM response, stripping markdown fences if present."""
    if not text:
        return None

    # strip ```json ... ``` or ``` ... ``` blocks
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to find the first {...} or [...] block
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return None
