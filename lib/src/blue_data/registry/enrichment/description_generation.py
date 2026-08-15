from __future__ import annotations

import json
from typing import Callable


class DescriptionGenerator:
    """Lightweight, standalone description generator.

    Generates natural-language descriptions for attributes, entities,
    collections, and databases. When ``llm_fn`` is provided, descriptions
    are produced by the LLM; otherwise a minimal template string is returned.
    """

    def __init__(self, llm_fn: Callable[[str], str] | None = None):
        self._llm_fn = llm_fn

    def _call_llm(self, prompt: str) -> str | None:
        if self._llm_fn is None:
            return None
        return self._llm_fn(prompt)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def build_attribute_description_prompt(self, attribute: dict) -> str:
        name = attribute.get("name", "unknown")
        props = attribute.get("properties", {}) or {}
        info = props.get("info", {}) or {}
        dtype = info.get("type", "unknown")
        stats = props.get("stats", {}) or {}
        sample_values = stats.get("sample_values", [])[:5]
        semantic_type = (props.get("metadata", {}) or {}).get("semantic_type", "")

        lines = [f"Name: {name}", f"Declared type: {dtype}"]
        if semantic_type:
            lines.append(f"Semantic type: {semantic_type}")
        if sample_values:
            lines.append(f"Sample values: {json.dumps(sample_values)}")

        return (
            "Generate a concise, one-sentence description for this database attribute.\n\n"
            + "\n".join(lines)
            + "\n\nReturn only the description text — no JSON, no formatting."
        )

    def build_entity_description_prompt(self, entity_name: str, attributes: list[dict]) -> str:
        attr_lines = []
        for a in attributes[:20]:
            aname = a.get("name", "?")
            dtype = (a.get("properties", {}) or {}).get("info", {}).get("type", "unknown")
            attr_lines.append(f"  - {aname} ({dtype})")
        attr_block = "\n".join(attr_lines) or "  (no attributes)"

        return (
            f"Generate a concise, one-sentence description for the database table '{entity_name}'.\n\n"
            f"Columns:\n{attr_block}\n\n"
            "Return only the description text — no JSON, no formatting."
        )

    def build_collection_description_prompt(self, collection_name: str, entity_descriptions: dict[str, str]) -> str:
        lines = [f"  - {n}: {d}" for n, d in entity_descriptions.items() if d]
        entity_block = "\n".join(lines) or "  (no entity descriptions available)"

        return (
            f"Generate a concise, one-sentence description for the database schema '{collection_name}'.\n\n"
            f"It contains the following tables:\n{entity_block}\n\n"
            "Return only the description text — no JSON, no formatting."
        )

    def build_database_description_prompt(self, database_name: str, collection_descriptions: dict[str, str]) -> str:
        lines = [f"  - {n}: {d}" for n, d in collection_descriptions.items() if d]
        coll_block = "\n".join(lines) or "  (no schema descriptions available)"

        return (
            f"Generate a concise, one-sentence description for the database '{database_name}'.\n\n"
            f"It contains the following schemas:\n{coll_block}\n\n"
            "Return only the description text — no JSON, no formatting."
        )

    # ------------------------------------------------------------------
    # Public generate methods
    # ------------------------------------------------------------------

    def generate_attribute_description(self, attribute: dict) -> str:
        result = self._call_llm(self.build_attribute_description_prompt(attribute))
        if result:
            return result.strip()
        name = attribute.get("name", "unknown")
        dtype = ((attribute.get("properties", {}) or {}).get("info", {}) or {}).get("type", "unknown")
        return f"Attribute `{name}` with type `{dtype}`."

    def generate_entity_description(self, entity_name: str, attributes: list[dict]) -> str:
        result = self._call_llm(self.build_entity_description_prompt(entity_name, attributes))
        if result:
            return result.strip()
        return f"Table `{entity_name}` with {len(attributes)} column(s)."

    def generate_collection_description(self, collection_name: str, entity_descriptions: dict[str, str]) -> str:
        result = self._call_llm(self.build_collection_description_prompt(collection_name, entity_descriptions))
        if result:
            return result.strip()
        return f"Schema `{collection_name}` containing {len(entity_descriptions)} table(s)."

    def generate_database_description(self, database_name: str, collection_descriptions: dict[str, str]) -> str:
        result = self._call_llm(self.build_database_description_prompt(database_name, collection_descriptions))
        if result:
            return result.strip()
        return f"Database `{database_name}` with {len(collection_descriptions)} schema(s)."
