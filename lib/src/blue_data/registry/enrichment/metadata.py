"""Metadata enrichment pipeline.

All LLM-based enrichments require an ``llm_fn`` callable to be injected at
construction time.  Without it every
LLM-dependent method silently returns ``None`` so deterministic enrichments
(process semantics, semantic links, value-axis inference, etc.) still run.

Property taxonomy stored on attribute records after enrichment:

    value_semantics           — VSI: rich semantic type + flags
    semantic_discovery        — SDI: open-world concept discovery
    domain_concept            — DCM: taxonomy concept mapping
    interpretive_sem.         — IVS: ordinal/severity/tier ordering
    value_axis                — magnitude / ordinal axis
    quantitative_vst          — quantitative role (MEASUREMENT / COUNT / …)
    safe_aggregation          — aggregation safety rules (can_sum, can_avg, forbidden_combinations)
    semantic_role             — IDENTIFIER / EVENT_TIME / SEGMENTATION_DRIVER / …
    role_query_constraints    — per-attribute query planning constraints (can_group_by, should_not_sum, …)
    process_vst_role          — PROCESS_KEY / EVENT_TIME / EVENT_MEASURE / STATE_VAR
    time_grain_candidates     — inferred time bucketing granularities (on event-time attributes)

Property taxonomy stored on entity records:

    semantic_links            — validated inter-attribute relationships
    total_component_measures  — TOTAL/COMPONENT numeric relationships (prevents double-counting)
    derived_metric_candidates — rate/ratio candidates for NL2SQL (e.g. injuries_per_event)
    process_semantics         — EVENT row semantics
    process_patterns          — temporal cadence
    process_trends            — trend direction per measure
    process_operators         — NL2SQL operators (AGGREGATE_OVER_TIME, CHANGE_DETECTION, …)
    process_query_constraints — query planner constraints from process operators
    conditional_value_distribution — P(value | group)
"""
from __future__ import annotations

import json
import logging
import math
import os
from itertools import combinations
from typing import Any, Callable

import numpy as np

from blue_data.registry.enrichment.prompts import AGGREGATION_PROMPT
from blue_data.core.utils.utils import safe_json_parse


class MetaData:
    """Rich metadata enrichment pipeline (LLM-augmented, deterministic fallback)."""

    # ------------------------------------------------------------------
    # Type taxonomies
    # ------------------------------------------------------------------

    VALUE_SEMANTIC_TYPES = [
        "UNKNOWN",
        # structural
        "BOOLEAN",
        "INTEGER",
        "FLOAT",
        "NUMERIC_GENERAL",
        "STRING",
        "FREE_TEXT",
        # temporal
        "DATE",
        "DATETIME",
        "TIME",
        "YEAR",
        "MONTH",
        "DAY_OF_WEEK",
        "DURATION",
        # location / codes
        "US_STATE_CODE",
        "US_STATE_NAME",
        "COUNTRY_CODE_ISO2",
        "COUNTRY_CODE_ISO3",
        "CITY_NAME",
        "POSTAL_CODE",
        "ADDRESS_FREEFORM",
        # financial / numeric semantics
        "CURRENCY_AMOUNT",
        "PERCENTAGE",
        "RATIO",
        # identity / ids
        "ID_NUMERIC",
        "ID_STRING",
        "UUID",
        "HASH",
        # contact / web
        "EMAIL",
        "PHONE_NUMBER",
        "URL",
        # categories & labels
        "ENUM_CATEGORY",
        "TEXT_CATEGORY",
        "TAG",
        "LABEL",
        # human / skills / terms
        "PERSON_NAME",
        "ORG_NAME",
        "JOB_TITLE",
        "SKILL_TERM",
        "CONTROLLED_TERM",
        # demographic
        "AGE",
        "AGE_GROUP",
        "DEMOGRAPHIC_TERM",
    ]

    SEMANTIC_ROLES = [
        "IDENTIFIER",
        "EVENT_TIME",
        "EVIDENCE",
        "SEGMENTATION_DRIVER",
        "DESCRIPTIVE",
    ]

    PROCESS_VST_ROLES = [
        "PROCESS_KEY",
        "EVENT_TIME",
        "EVENT_MEASURE",
        "STATE_VARIABLE",
    ]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        llm_fn: Callable[[str], str] | None = None,
        taxonomy: list[str] | None = None,
        taxonomy_path: str | None = None,
        properties: dict | None = None,
    ):
        """
        Args:
            llm_fn: Provider-agnostic LLM callable ``(prompt: str) -> str``.
                When ``None`` all LLM-dependent steps are skipped; deterministic
                enrichments (process semantics, semantic links, value-axis, etc.)
                still run.
            taxonomy: Pre-loaded list of domain concept strings
                (e.g. ``["CONCEPT.PERSON.NAME", "CONCEPT.FINANCE.AMOUNT"]``).
                Takes precedence over ``taxonomy_path``.
            taxonomy_path: Path to a JSON file with shape ``{"concepts": [...]}``.
                Used when the taxonomy is stored on disk. Ignored if ``taxonomy``
                is provided. DCM is disabled when neither is supplied.
            properties: Feature-flag overrides. Any key set here takes precedence
                over the defaults (e.g. ``{"enable_process_semantics_inference": False}``).
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self._llm_fn = llm_fn

        self._taxonomy: list[str] = taxonomy or self._load_taxonomy(taxonomy_path)

        # feature flags — all on by default; caller can disable selectively
        self.properties: dict[str, Any] = {
            "enable_entity_description_generation": True,
            "enable_attribute_description_generation": True,
            "enable_database_description_generation": True,
            "enable_collection_description_generation": True,
            "enable_value_semantics_inference": True,
            "enable_semantic_discovery_inference": True,
            "enable_domain_concept_mapping": bool(self._taxonomy),
            "enable_value_axis_inference": True,
            "enable_semantic_links_inference": True,
            "enable_interpretive_semantics": True,
            "enable_process_semantics_inference": True,
            "enable_quantitative_semantics_inference": True,
            "enable_total_component_detection": True,
            "enable_safe_aggregation_inference": True,
            "enable_derived_metric_candidates": True,
            "enable_process_operator_semantics": True,
            "enable_role_query_constraints": True,
        }
        if properties:
            self.properties.update(properties)

        # mutable context shared within a single entity enrichment pass
        self.current_entity_row_samples: list[dict] = []
        self.current_entity_attributes: list[dict] = []

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> str | None:
        if self._llm_fn is None:
            return None
        try:
            return self._llm_fn(prompt)
        except Exception as e:
            self.logger.warning(f"LLM call failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------

    def _load_taxonomy(self, path: str | None) -> list[str]:
        if not path or not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                data = json.load(f)
                return data.get("concepts", [])
        except Exception as e:
            self.logger.error(f"Failed loading taxonomy: {e}")
            return []

    # ------------------------------------------------------------------
    # Math helpers
    # ------------------------------------------------------------------

    @staticmethod
    def mean_safe(vals: list) -> float | None:
        return sum(vals) / len(vals) if vals else None

    @staticmethod
    def safe_pearson(x: list, y: list) -> float:
        if len(x) < 5 or len(y) < 5:
            return 0.0
        mx, my = sum(x) / len(x), sum(y) / len(y)
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        denx = math.sqrt(sum((a - mx) ** 2 for a in x))
        deny = math.sqrt(sum((b - my) ** 2 for b in y))
        if denx == 0 or deny == 0:
            return 0.0
        return num / (denx * deny)

    @staticmethod
    def get_numeric_samples(attr: dict) -> list[float]:
        stats = attr.get("properties", {}).get("stats", {})
        nums = []
        for v in stats.get("sample_values", []):
            try:
                nums.append(float(v))
            except Exception:
                pass
        return nums

    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------

    def has_row_cooccurrence(self, a: dict, b: dict, row_samples: list, min_rows: int = 5) -> bool:
        a_name, b_name = a["name"], b["name"]
        count = 0
        for row in row_samples:
            if row.get(a_name) is not None and row.get(b_name) is not None:
                count += 1
                if count >= min_rows:
                    return True
        return False

    def functional_dependency_signal(self, a: dict, b: dict) -> bool:
        a_vals = self.get_numeric_samples(a)
        b_vals = self.get_numeric_samples(b)
        if len(a_vals) < 5 or len(b_vals) < 5:
            return False
        return abs(self.safe_pearson(a_vals, b_vals)) > 0.7

    def temporal_alignment_signal(self, a: dict, b: dict) -> bool:
        temporal = {"DATE", "DATETIME", "TIME", "DURATION"}
        a_type = a.get("properties", {}).get("value_semantics", {}).get("semantic_type")
        b_type = b.get("properties", {}).get("value_semantics", {}).get("semantic_type")
        return a_type in temporal and b_type not in temporal

    def grouped_distribution_signal(self, group_attr: dict, value_attr: dict) -> bool:
        g_vals = group_attr.get("properties", {}).get("stats", {}).get("sample_values", [])
        v_vals = value_attr.get("properties", {}).get("stats", {}).get("sample_values", [])
        if not g_vals or not v_vals:
            return False
        try:
            groups: dict[Any, list] = {}
            for g, v in zip(g_vals, v_vals):
                try:
                    v = float(v)
                except Exception:
                    continue
                groups.setdefault(g, []).append(v)

            if len(groups) < 2:
                return False
            if sum(1 for vals in groups.values() if len(vals) >= 2) < 2:
                return False

            means = [sum(vals) / len(vals) for vals in groups.values()]
            max_mean = max(abs(m) for m in means) if means else 0.0
            if max_mean == 0:
                return False

            spread = max(means) - min(means)
            avg_mean = sum(abs(m) for m in means) / len(means)
            relative_spread = spread / avg_mean if avg_mean > 0 else 0.0
            return spread > 0.12 * max_mean or relative_spread > 0.18
        except Exception:
            return False

    def grouped_distribution_signal_row_aligned(
        self, group_attr: dict, value_attr: dict, row_samples: list
    ) -> bool:
        g_name, v_name = group_attr["name"], value_attr["name"]
        g_vals, v_vals = [], []
        for row in row_samples:
            g = row.get(g_name)
            v = row.get(v_name)
            if g is None or v is None:
                continue
            try:
                v_vals.append(float(v))
                g_vals.append(g)
            except Exception:
                pass
        if len(g_vals) < 5:
            return False
        return self.grouped_distribution_signal(
            {"properties": {"stats": {"sample_values": g_vals}}},
            {"properties": {"stats": {"sample_values": v_vals}}},
        )

    def is_sparse_count_axis(self, attr: dict, values: list) -> bool:
        if not values:
            return False
        vsi = attr.get("properties", {}).get("value_semantics", {})
        if vsi.get("semantic_type") not in {"INTEGER", "NUMERIC_GENERAL"}:
            return False
        name = attr.get("name", "").lower()
        if name in {"latitude", "longitude", "lat", "lon", "lng"}:
            return False
        if not vsi.get("numeric", {}).get("is_discrete", True):
            return False
        n = len(values)
        zero_frac = sum(v == 0 for v in values) / n
        max_val = max(values)
        distinct = len(set(values))
        if zero_frac >= 0.7 and distinct <= 10:
            return True
        if zero_frac >= 0.4 and max_val >= 5:
            return True
        return False

    def infer_tail_threshold(self, values: list) -> int | None:
        values = sorted(values)
        n = len(values)
        non_zero = [v for v in values if v > 0]
        if not non_zero:
            return None
        if max(non_zero) <= 3:
            return 1
        for t in [5, 10, 15, 20]:
            if sum(v >= t for v in values) / n < 0.01:
                return t
        return max(values)

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def build_attribute_context(self, attributes: list, target_attr_name: str) -> dict:
        context: dict = {
            "sibling_attributes": [],
            "numeric_distributions": {},
            "temporal_hints": [],
            "co_occurrence_hints": [],
            "relative_behavior": [],
        }
        for attr in attributes:
            name = attr.get("name")
            if name == target_attr_name:
                continue
            props = attr.get("properties", {}) or {}
            stats = props.get("stats", {}) or {}
            sem = props.get("value_semantics", {}) or {}
            samples = stats.get("sample_values", [])[:5]

            context["sibling_attributes"].append(name)

            min_val, max_val = stats.get("min"), stats.get("max")
            is_numeric = isinstance(min_val, (int, float)) or isinstance(max_val, (int, float))
            if is_numeric:
                context["numeric_distributions"][name] = {
                    "min": min_val,
                    "max": max_val,
                    "distinct": stats.get("distinct_count"),
                }
                if not sem.get("is_identifier") and isinstance(max_val, (int, float)):
                    context["relative_behavior"].append({
                        "attribute": name,
                        "scale_hint": (
                            "small_range" if max_val < 100
                            else "medium_range" if max_val < 10000
                            else "large_range"
                        ),
                    })

            if sem.get("semantic_type") in ("DATE", "DATETIME", "DURATION"):
                context["temporal_hints"].append(name)

            if samples:
                context["co_occurrence_hints"].append({"attribute": name, "sample_values": samples})

        if len(context["relative_behavior"]) >= 2:
            context["relative_behavior_summary"] = {
                "comparison": [(rb["attribute"], rb["scale_hint"]) for rb in context["relative_behavior"]]
            }
        return context

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def build_entity_description_prompt(self, entity_obj: dict, attributes: list) -> str:
        name = entity_obj.get("name", "Unknown")
        scope = entity_obj.get("scope", "Unknown")
        etype = entity_obj.get("type", "Unknown")
        attr_lines = []
        for attr in attributes:
            props = attr.get("properties", {})
            attr_type = props.get("info", {}).get("type", "unknown")
            attr_name = attr.get("name")
            samples = props.get("stats", {}).get("sample_values", [])
            attr_lines.append(
                f"- {attr_name} ({attr_type}), samples: {', '.join(map(str, samples[:3]))}"
            )
        return f"""
You are given a database entity definition with its attributes and metadata.
Your task is to generate a structured JSON output with:
1. A concise human-readable description of what this table/entity represents.
2. Concise descriptions of each attribute.

Entity Name: {name}
Scope: {scope}
Type: {etype}

Attributes:
{chr(10).join(attr_lines)}

Output JSON format (do not include extra commentary, only valid JSON):
{{
  "table_description": "string",
  "attributes": {{
    "attr_name": "description of attribute"
  }}
}}
""".strip()

    def build_vsi_prompt(self, entity_name: str, attr_name: str, attr_properties: dict, context: dict | None = None) -> str:
        stats = attr_properties.get("stats", {}) or {}
        sample_values = stats.get("sample_values", [])[:10] or ["<NO SAMPLE VALUES AVAILABLE>"]
        attr_type = attr_properties.get("info", {}).get("type", "unknown")

        schema_json = """{
  "value_semantics": {
    "primary_type": "<ONE_OF_ALLOWED_TYPES>",
    "secondary_types": [],
    "is_categorical": false,
    "is_identifier": false,
    "is_free_text": false,
    "numeric": {
      "is_numeric": false,
      "is_continuous": false,
      "is_discrete": false,
      "min": null,
      "max": null
    },
    "temporal": {
      "is_date": false,
      "is_datetime": false,
      "is_duration": false,
      "granularity": null
    },
    "normalization": {
      "can_normalize": false,
      "normalized_examples": [],
      "normalization_strategy": null
    },
    "confidence": 0.0,
    "examples_used": [],
    "notes": []
  }
}"""

        return f"""
You are performing Value Semantics Inference (VSI).
Infer WHAT THE VALUES *ARE*, not what they represent in the domain.

Rules:
- Use ONLY value patterns + statistics.
- You MAY use other attributes ONLY for structural AND distributional disambiguation.
- Use ONLY allowed semantic types.
- DO NOT invent new types. Stay within allowed types.

ATTRIBUTE CONTEXT
Entity: {entity_name}
Attribute: {attr_name}
Declared Type: {attr_type}

ATTRIBUTE_STATS:
{json.dumps(stats, indent=2)}

SAMPLE_VALUES:
{json.dumps(sample_values, indent=2)}

OTHER_ATTRIBUTES_IN_ENTITY (contextual structural hints only):
{json.dumps(context or {}, indent=2)}

ALLOWED_SEMANTIC_TYPES:
{json.dumps(self.VALUE_SEMANTIC_TYPES, indent=2)}

OUTPUT FORMAT (STRICT JSON ONLY):
{schema_json}

Return ONLY this JSON structure, filled in appropriately.
""".strip()

    def build_sdi_prompt(self, entity_name: str, attr_name: str, attr_properties: dict, context: dict | None = None) -> str:
        """Open-world SDI prompt. Generates new semantic types when the closed VSI taxonomy does not fit."""
        stats = attr_properties.get("stats", {}) or {}
        sample_values = stats.get("sample_values", [])[:10] or ["<NO SAMPLE VALUES AVAILABLE>"]
        attr_type = attr_properties.get("info", {}).get("type", "unknown")

        return f"""
You are an advanced semantic discovery engine designed for enterprise-scale,
heterogeneous data. Your goal is to infer the **intrinsic semantic meaning** of the VALUES
in a database attribute — based only on the values themselves, not business rules.

──────────────────────────────────────────────
SEMANTIC DISCOVERY (SDI) — CORE PRINCIPLES
──────────────────────────────────────────────
You operate under an OPEN-WORLD semantic model:

1. SDI is NOT a closed taxonomy.
2. You may generate new semantic types if supported by patterns in the values.
3. You infer meaning by analyzing:
   • linguistic patterns
   • structural patterns
   • categorical signals
   • statistical regularities
   • latent real-world semantics

Never restrict yourself to predefined categories.

──────────────────────────────────────────────
THE THREE-LAYER SEMANTIC MODEL
──────────────────────────────────────────────

LAYER 1 — STRUCTURAL SEMANTICS
    What *shape* do the values have?
    Examples: STRING, NUMBER, INTEGER, DATE, URL, EMAIL, ID_STRING, BOOLEAN, CODE

LAYER 2 — LINGUISTIC / ENTITY SEMANTICS
    What *type of entity or label* do the values resemble?
    Examples (not exhaustive): person names, job titles, certification names,
    skills or competencies, locations, product names, organizational entities.
    These categories are open-world: you may create new ones.

LAYER 3 — CONCEPTUAL / CATEGORY SEMANTICS
    What *semantic class or conceptual grouping* do the values imply?
    This includes: demographic groups (teenagers, seniors), vehicle classes
    (heavy truck, light truck), risk/quality tiers, product tiers (premium, basic),
    salary or value levels, measurement categories (speed, volume, weight).
    This is open-world: you may generate new conceptual classes.

IMPORTANT: These layers are not mutually exclusive — produce the *most informative*
semantic type that best describes the values.

──────────────────────────────────────────────
GENERALIZED DETECTION PATTERNS
──────────────────────────────────────────────

• STRUCTURAL SIGNALS: formats (dates, codes, emails, numbers), token patterns,
  length consistency, character composition.

• LINGUISTIC SIGNALS: multi-word phrases, professional titles, credential-like
  structures ("Certified…", "Diploma in…"), named entities (locations, organizations),
  labels with standardised wording (hazard class, tier labels).

• CATEGORY SIGNALS: group names ("teenagers", "seniors"), categorical adjectives
  (high, low, premium, hazardous), domain-like clusters, ordinal or tiered values.

• NUMERIC SEMANTICS: if values *represent* categories (not numbers), infer:
    – ranges (age group, tier)
    – thresholds (heavy truck → payload > X)
    – levels (risk, salary, quality)

──────────────────────────────────────────────
WHEN TO USE FREE_TEXT
──────────────────────────────────────────────
ONLY use FREE_TEXT if:
1. Values show no consistent structure,
2. No stable linguistic or categorical signals exist,
3. Values are arbitrary human-written sentences with no common semantic class.
This should be rare.

──────────────────────────────────────────────
ATTRIBUTE CONTEXT
──────────────────────────────────────────────
Entity: {entity_name}
Attribute: {attr_name}
Declared Type: {attr_type}

Sample Values:
{json.dumps(sample_values, indent=2)}

Cross-attribute context (optional evidence — use ONLY to discover latent groupings,
thresholds, or fuzzy categories; do NOT assign roles or enforce column consistency):
{json.dumps(context or {}, indent=2)}

──────────────────────────────────────────────
OUTPUT FORMAT (STRICT JSON ONLY)
──────────────────────────────────────────────
{{
  "semantic_type": "string",
  "subcategory": "string or null",
  "confidence": 0.0,
  "range": {{"min": null, "max": null}},
  "criteria": "string or null",
  "rationale": "short explanation of the inferred semantics",
  "examples": []
}}

INTERPRETATION GUIDELINES:
- semantic_type: most informative object-level category.
- subcategory: refinement (e.g. HEAVY_TRUCK, TEENAGER, PREMIUM).
- range: only when applicable (ages, thresholds, numeric groups).
- criteria: inferred thresholds or rules.
- examples: must be drawn from the provided sample values.

Now infer the most accurate semantics and return ONLY valid JSON.
""".strip()

    def build_domain_concept_prompt(self, entity_name: str, attr_name: str, attr_properties: dict) -> str:
        taxonomy_text = (
            "\n".join(f"- {c}" for c in self._taxonomy) if self._taxonomy else "- CONCEPT.UNKNOWN"
        )
        semantics = attr_properties.get("value_semantics", {})
        semantic_type = semantics.get("semantic_type", "UNKNOWN")
        sdi = attr_properties.get("semantic_discovery", {})
        sample_values = (
            semantics.get("examples", [])
            or attr_properties.get("stats", {}).get("sample_values", [])[:5]
            or ["<NO SAMPLE VALUES AVAILABLE>"]
        )
        return f"""
You are performing domain concept mapping for a data registry.
Map the attribute to a canonical DOMAIN CONCEPT.

Available domain concepts:
{taxonomy_text}

Attribute Context:
- Entity: {entity_name}
- Attribute Name: {attr_name}
- Semantic Type: {semantic_type}

Semantic Discovery Output (SDI):
{json.dumps(sdi, indent=2)}

Sample Values:
{json.dumps(sample_values, indent=2)}

Output JSON ONLY:
{{
  "concept": "CONCEPT.X.Y",
  "confidence": 0.0,
  "rationale": "explain briefly"
}}
""".strip()

    def build_interpretive_semantics_prompt(self, entity_name: str, attr_name: str, attr_properties: dict) -> str:
        stats = attr_properties.get("stats", {})
        samples = stats.get("sample_values", [])[:10]
        sdi = attr_properties.get("semantic_discovery", {})
        vsi = attr_properties.get("value_semantics", {})

        return f"""
You are performing INTERPRETIVE VALUE SEMANTICS (IVS).

Infer WHETHER the categorical values imply an ORDERING, SEVERITY, or TIER
that an intelligent agent might use when reasoning.

SAFETY RULES:
- Do NOT assume meaning unless strongly implied.
- If ordering is ambiguous, return interpretation_type = "NONE".
- This output is OPTIONAL and MUST NOT be treated as ground truth.

ATTRIBUTE CONTEXT
Entity: {entity_name}
Attribute: {attr_name}

Sample Values:
{json.dumps(samples, indent=2)}

Value Semantics (VSI):
{json.dumps(vsi, indent=2)}

Semantic Discovery (SDI):
{json.dumps(sdi, indent=2)}

INTERPRETATION TYPES:
ORDINAL   — ordered categories (A < B < C)
SEVERITY  — worse/better progression
TIER      — product/quality levels
NONE      — no safe interpretation

OUTPUT FORMAT (STRICT JSON):
{{
  "interpretation_type": "ORDINAL | SEVERITY | TIER | NONE",
  "ordering": [],
  "polarity": {{
    "direction": "increasing | decreasing",
    "meaning": "risk | severity | quality | preference | level"
  }},
  "confidence": 0.0,
  "rationale": "short explanation",
  "evidence": {{"examples": [], "source": "labels | SDI | linguistic"}}
}}
""".strip()

    def build_semantic_link_validation_prompt(self, source: dict, target: dict, signal: Any) -> str:
        src_vs = source.get("properties", {}).get("value_semantics", {})
        tgt_vs = target.get("properties", {}).get("value_semantics", {})
        return f"""
You are validating a semantic relationship between two attributes.

Source attribute:
- Name: {source.get('name', 'UNKNOWN')}
- Semantic type: {src_vs.get('semantic_type', 'UNKNOWN')}

Target attribute:
- Name: {target.get('name', 'UNKNOWN')}
- Semantic type: {tgt_vs.get('semantic_type', 'UNKNOWN')}

Observed signal: {signal}

Choose ONE relationship: SEGMENTS / DERIVES / SUPPORTS / ASSOCIATED / UNRELATED

Return JSON ONLY:
{{
  "relationship": "...",
  "confidence": 0.0,
  "rationale": "short explanation"
}}
""".strip()

    def build_collection_description_prompt(self, collection_name: str, entity_descriptions: dict, collection_metadata: Any) -> str:
        children = [f"{n}: {d}" for n, d in entity_descriptions.items() if d] or ["No entity descriptions available"]
        return AGGREGATION_PROMPT.format(
            child_type="entity",
            parent_type="collection",
            child_descriptions="\n".join(children),
            parent_metadata=f"Collection name: {collection_name}\nMetadata: {collection_metadata}",
        )

    def build_database_description_prompt(self, database_name: str, collection_descriptions: dict, database_metadata: Any) -> str:
        children = [f"{n}: {d}" for n, d in collection_descriptions.items() if d] or ["No collection descriptions available"]
        return AGGREGATION_PROMPT.format(
            child_type="collection",
            parent_type="database",
            child_descriptions="\n".join(children),
            parent_metadata=f"Database name: {database_name}\nMetadata: {database_metadata}",
        )

    # ------------------------------------------------------------------
    # LLM-based enrichers
    # ------------------------------------------------------------------

    def enrich_entity(self, entity: dict, attributes: list) -> str | None:
        prompt = self.build_entity_description_prompt(entity, attributes)
        return self._call_llm(prompt)

    def enrich_collection_description(self, collection_name: str, entity_descriptions: dict, collection_metadata: Any) -> str | None:
        return self._call_llm(self.build_collection_description_prompt(collection_name, entity_descriptions, collection_metadata))

    def enrich_database_description(self, database_name: str, collection_descriptions: dict, database_metadata: Any) -> str | None:
        return self._call_llm(self.build_database_description_prompt(database_name, collection_descriptions, database_metadata))

    def infer_attribute_vsi(self, entity_name: str, attr: dict) -> dict | None:
        """Run closed-world VSI for a single attribute via LLM.

        Returns the parsed ``value_semantics`` dict, or ``None`` if the LLM is
        unavailable or the response cannot be parsed.
        """
        attr_name = attr.get("name")
        props = attr.get("properties", {})
        context = self.build_attribute_context(self.current_entity_attributes, attr_name)
        prompt = self.build_vsi_prompt(entity_name, attr_name, props, context=context)
        raw = self._call_llm(prompt)
        if raw is None:
            return None
        try:
            parsed = safe_json_parse(raw)
            if not parsed:
                return None
            vs = parsed.get("value_semantics", parsed)
            if "primary_type" in vs:
                vs["semantic_type"] = vs.get("primary_type")
            return vs
        except Exception:
            self.logger.warning(f"Invalid VSI JSON for {entity_name}.{attr_name}")
            return None

    def infer_attribute_sdi(self, entity_name: str, attr: dict) -> dict | None:
        """Run open-world SDI for a single attribute via LLM.

        Returns the parsed ``semantic_discovery`` dict, or ``None`` if the LLM
        is unavailable or the response cannot be parsed.
        """
        attr_name = attr.get("name")
        props = attr.get("properties", {})
        context = self.build_attribute_context(self.current_entity_attributes, attr_name)
        prompt = self.build_sdi_prompt(entity_name, attr_name, props, context=context)
        raw = self._call_llm(prompt)
        if raw is None:
            return None
        try:
            return safe_json_parse(raw)
        except Exception:
            self.logger.warning(f"Invalid SDI JSON for {entity_name}.{attr_name}")
            return None

    def infer_domain_concept(self, entity_name: str, attr: dict) -> dict | None:
        """Map an attribute to a canonical domain concept from the taxonomy via LLM.

        Skipped when ``value_semantics`` has not yet been written to the attribute
        (VSI must run first). Returns ``None`` when the LLM is unavailable, the
        taxonomy is empty, or the response cannot be parsed.
        """
        if "value_semantics" not in attr.get("properties", {}):
            return None
        prompt = self.build_domain_concept_prompt(entity_name, attr.get("name"), attr.get("properties", {}))
        raw = self._call_llm(prompt)
        if raw is None:
            return None
        try:
            return safe_json_parse(raw)
        except Exception:
            self.logger.warning(f"Invalid domain concept JSON for {entity_name}.{attr.get('name')}")
            return None

    def infer_interpretive_semantics(self, entity_name: str, attr: dict) -> dict | None:
        """Infer whether categorical values carry an implicit ordering, severity, or tier (IVS).

        Only runs for ``ENUM_CATEGORY`` and ``TEXT_CATEGORY`` attributes that are
        not identifiers. Returns ``None`` when the attribute is ineligible, the
        LLM is unavailable, confidence is below 0.6, or interpretation type is NONE.
        """
        vsi = attr.get("properties", {}).get("value_semantics", {})
        if vsi.get("is_identifier"):
            return None
        if vsi.get("semantic_type") not in ("ENUM_CATEGORY", "TEXT_CATEGORY"):
            return None
        prompt = self.build_interpretive_semantics_prompt(entity_name, attr["name"], attr.get("properties", {}))
        raw = self._call_llm(prompt)
        if raw is None:
            return None
        try:
            parsed = safe_json_parse(raw)
            if not parsed:
                return None
            if parsed.get("interpretation_type") == "NONE":
                return None
            if parsed.get("confidence", 0) < 0.6:
                return None
            return parsed
        except Exception:
            self.logger.warning(f"Invalid IVS JSON for {entity_name}.{attr['name']}")
            return None

    def validate_semantic_link(self, source: dict, target: dict, signal: Any) -> dict | None:
        prompt = self.build_semantic_link_validation_prompt(source, target, signal)
        raw = self._call_llm(prompt)
        if raw is None:
            return None
        return safe_json_parse(raw)

    # ------------------------------------------------------------------
    # Statistical link pre-validation (deterministic, runs before LLM)
    # ------------------------------------------------------------------

    def validate_segments_signal(self, a: dict, b: dict, row_samples: list) -> bool:
        """Return True if *a* has bounded cardinality and meaningfully segments *b*."""
        if not self.has_row_cooccurrence(a, b, row_samples, min_rows=5):
            return False
        a_vals = [row.get(a["name"]) for row in row_samples if row.get(a["name"]) is not None]
        distinct_groups = len(set(str(v) for v in a_vals))
        if distinct_groups < 2 or distinct_groups > 20:
            return False
        return self.grouped_distribution_signal_row_aligned(a, b, row_samples)

    def validate_temporal_alignment_signal(self, a: dict, b: dict, row_samples: list) -> bool:
        """Return True if *a* is temporal, *b* is not, and they co-occur in rows."""
        if not self.temporal_alignment_signal(a, b):
            return False
        return self.has_row_cooccurrence(a, b, row_samples, min_rows=5)

    def validate_cooccurrence_signal(self, a: dict, b: dict, row_samples: list) -> bool:
        """Return True if *a* and *b* appear together in enough rows."""
        return self.has_row_cooccurrence(a, b, row_samples, min_rows=5)

    def validate_relational_link_signal(self, a: dict, b: dict, signal: Any, row_samples: list) -> bool:
        """Pre-validate a candidate semantic link against row samples before calling the LLM.

        Returns False to reject links with insufficient statistical support,
        saving LLM calls for clearly weak signals.
        """
        signal_type = signal.get("type") if isinstance(signal, dict) else signal
        if signal_type == "grouped_distribution":
            return self.validate_segments_signal(a, b, row_samples)
        if signal_type == "temporal_alignment":
            return self.validate_temporal_alignment_signal(a, b, row_samples)
        if signal_type == "functional_dependency":
            return self.validate_cooccurrence_signal(a, b, row_samples)
        return True  # unknown signal type — let LLM decide

    # ------------------------------------------------------------------
    # Deterministic enrichers
    # ------------------------------------------------------------------

    def infer_semantic_links(self, attributes: list) -> list[dict]:
        links = []
        for i, a in enumerate(attributes):
            for j, b in enumerate(attributes):
                if a["name"] == b["name"]:
                    continue
                if self.grouped_distribution_signal(a, b):
                    links.append({"source": a["name"], "target": b["name"], "signal": "grouped_distribution", "row_support": False})
                # Pearson is symmetric — only add each pair once (lower index → higher)
                if i < j and self.functional_dependency_signal(a, b):
                    links.append({"source": a["name"], "target": b["name"], "signal": {"type": "functional_dependency", "strength": 0.7}})
        return links

    def infer_row_based_links(self, attributes: list, row_samples: list) -> list[dict]:
        links = []
        if not row_samples:
            return links
        temporal = {"DATE", "DATETIME", "TIME", "DURATION"}
        for a in attributes:
            for b in attributes:
                if a["name"] == b["name"]:
                    continue
                if self.grouped_distribution_signal_row_aligned(a, b, row_samples):
                    links.append({"source": a["name"], "target": b["name"], "signal": "grouped_distribution", "row_support": True})
                a_type = a.get("properties", {}).get("value_semantics", {}).get("semantic_type")
                b_type = b.get("properties", {}).get("value_semantics", {}).get("semantic_type")
                if (a_type in temporal and b_type not in temporal and self.has_row_cooccurrence(a, b, row_samples)):
                    links.append({"source": a["name"], "target": b["name"], "signal": {"type": "temporal_alignment", "strength": 0.6, "row_support": True}})
        return links

    def infer_semantic_role(self, target_attr: dict, all_attrs: list, semantic_links: list | None = None) -> dict | None:
        semantic_links = semantic_links or []
        attr_name = target_attr["name"]
        vsi = target_attr.get("properties", {}).get("value_semantics", {})
        primary_type = vsi.get("semantic_type", "UNKNOWN")
        stats = target_attr.get("properties", {}).get("stats", {}) or {}

        # 1. Explicit identifier flag (set by LLM in Layer 2 VSI)
        if vsi.get("is_identifier"):
            return {"primary_role": "IDENTIFIER", "confidence": 0.95, "role_arguments": {}, "justification": {"rule": "identifier_flag"}}

        # 2. Name-based identifier heuristic (Layer 1): columns named "id" or ending
        #    in "_id" with an integer/string type are almost always PKs or FKs.
        name_lower = attr_name.lower()
        is_id_name = (name_lower == "id" or name_lower.endswith("_id"))
        if is_id_name and primary_type in ("INTEGER", "ID_NUMERIC", "STRING", "UUID", "HASH"):
            return {"primary_role": "IDENTIFIER", "confidence": 0.85, "role_arguments": {}, "justification": {"rule": "id_name_heuristic"}}

        # 3. DATE/DATETIME → EVENT_TIME before link-based checks so that a date
        #    column with incidental co-variation is not mis-classified as EVIDENCE.
        if primary_type in ("DATE", "DATETIME"):
            return {"primary_role": "EVENT_TIME", "confidence": 0.75, "role_arguments": {}, "justification": {"type_prior": primary_type}}

        outgoing = [l for l in semantic_links if l["source"] == attr_name]

        # 4. SEGMENTS links → SEGMENTATION_DRIVER
        segment_links = [
            l for l in outgoing
            if l.get("relationship") == "SEGMENTS"
            and not next((a for a in all_attrs if a["name"] == l["target"] and a.get("properties", {}).get("value_semantics", {}).get("is_identifier")), None)
        ]
        if segment_links:
            return {
                "primary_role": "SEGMENTATION_DRIVER",
                "confidence": min(0.95, sum(l.get("confidence", 0.7) for l in segment_links) / len(segment_links)),
                "role_arguments": {"segments": [l["target"] for l in segment_links]},
                "justification": {"signals": ["SEGMENTS"], "link_count": len(segment_links)},
            }

        # 5. SUPPORTS links → EVIDENCE
        supports = [l for l in outgoing if l.get("relationship") == "SUPPORTS"]
        if supports:
            return {
                "primary_role": "EVIDENCE",
                "confidence": min(0.9, sum(l.get("confidence", 0.7) for l in supports) / len(supports)),
                "role_arguments": {"supports": [l["target"] for l in supports]},
                "justification": {"signals": ["SUPPORTS"]},
            }

        # 6. Numeric measure fallback: continuous numeric columns with no links are
        #    almost always quantitative measures, not decorative descriptors.
        if primary_type in ("FLOAT", "INTEGER", "CURRENCY_AMOUNT", "PERCENTAGE", "RATIO"):
            return {"primary_role": "EVIDENCE", "confidence": 0.55, "role_arguments": {}, "justification": {"rule": "numeric_measure_fallback"}}

        return {"primary_role": "DESCRIPTIVE", "confidence": 0.4, "role_arguments": {}, "justification": {"reason": "no causal or statistical signals detected"}}

    # --- value axis ---

    def is_value_axis_eligible(self, attr: dict) -> bool:
        vsi = attr.get("properties", {}).get("value_semantics", {}) or {}
        if vsi.get("is_identifier"):
            return False
        semantic_type = vsi.get("semantic_type", "UNKNOWN")
        if semantic_type in {"ID_STRING", "ID_NUMERIC", "UUID", "HASH", "CODE", "TAG", "LABEL", "ENUM_CATEGORY", "TEXT_CATEGORY"}:
            return False
        return semantic_type in {"CURRENCY_AMOUNT", "INTEGER", "FLOAT", "NUMERIC_GENERAL", "PERCENTAGE", "RATIO", "DURATION"}

    def is_ivs_promotable_to_value_axis(self, attr: dict) -> bool:
        props = attr.get("properties", {})
        ivs = props.get("interpretive_semantics", {})
        vsi = props.get("value_semantics", {})
        if not ivs:
            return False
        if ivs.get("interpretation_type") not in ("ORDINAL", "TIER", "SEVERITY"):
            return False
        if ivs.get("confidence", 0.0) < 0.7:
            return False
        if vsi.get("is_identifier"):
            return False
        return vsi.get("semantic_type") in ("ENUM_CATEGORY", "TEXT_CATEGORY", "LABEL")

    def infer_numeric_value_axis(self, attr: dict, row_samples: list) -> dict | None:
        name = attr["name"]
        values = []
        for row in row_samples:
            try:
                values.append(float(row.get(name)))
            except Exception:
                pass
        if len(values) < 20:
            return None

        if self.is_sparse_count_axis(attr, values):
            threshold = self.infer_tail_threshold(values) or 1
            return {
                "axis_type": "DISCRETE_COUNT",
                "polarity": {"direction": "increasing", "meaning": "severity"},
                "extreme_regions": {"large": f">= {threshold}"},
                "confidence": 0.85,
                "rationale": "Sparse, zero-inflated discrete counts; extremes inferred via tail-regime semantics",
            }

        p10 = float(np.percentile(values, 10))
        p90 = float(np.percentile(values, 90))
        return {
            "axis_type": "CONTINUOUS",
            "polarity": {"direction": "increasing", "meaning": "magnitude"},
            "extreme_regions": {"small": f"< {round(p10, 2)}", "large": f"> {round(p90, 2)}"},
            "confidence": 0.7,
            "rationale": "Distributional extremes inferred via quantiles",
        }

    def infer_value_axis(self, attributes: list, row_samples: list) -> dict[str, dict]:
        axes: dict[str, dict] = {}
        numeric_types = {"CURRENCY_AMOUNT", "INTEGER", "FLOAT", "NUMERIC_GENERAL", "PERCENTAGE", "RATIO", "DURATION"}

        for attr in attributes:
            if not self.is_value_axis_eligible(attr):
                continue
            if attr.get("properties", {}).get("value_semantics", {}).get("semantic_type") in numeric_types:
                axis = self.infer_numeric_value_axis(attr, row_samples)
                if axis:
                    axes[attr["name"]] = axis

        for attr in attributes:
            name = attr["name"]
            if name in axes or not self.is_ivs_promotable_to_value_axis(attr):
                continue
            ivs = attr.get("properties", {}).get("interpretive_semantics")
            if not ivs:
                continue
            axes[name] = {
                "axis_type": "ORDINAL",
                "ordering": ivs.get("ordering", []),
                "polarity": ivs.get("polarity", {}),
                "extreme_regions": {
                    "low": ivs.get("ordering", [])[:1],
                    "high": ivs.get("ordering", [])[-1:],
                },
                "confidence": ivs.get("confidence", 0.7),
                "rationale": "Promoted from interpretive semantics",
                "source": "interpretive_semantics",
            }
        return axes

    # --- quantitative VST ---

    def infer_quantitative_vst_role(self, attr: dict) -> dict | None:
        props = attr.get("properties", {}) or {}
        vsi = props.get("value_semantics", {}) or {}
        semantic_type = vsi.get("semantic_type")
        name = attr.get("name", "").lower()
        nums = self.get_numeric_samples(attr)
        if not nums:
            return None

        axis = props.get("value_axis")
        if axis:
            if axis.get("axis_type") == "DISCRETE_COUNT":
                return {"role": "COUNT", "confidence": 0.9, "rationale": "Sparse discrete count via value axis"}
            if axis.get("axis_type") == "CONTINUOUS":
                return {"role": "MEASUREMENT", "confidence": 0.85, "rationale": "Continuous magnitude via value axis"}

        if semantic_type in {"CURRENCY_AMOUNT", "DURATION"}:
            return {"role": "MEASUREMENT", "confidence": 0.9, "rationale": f"{semantic_type} represents measurable quantity"}
        if semantic_type in {"PERCENTAGE", "RATIO"}:
            return {"role": "COMPUTATIONAL", "confidence": 0.85, "rationale": "Derived or normalized metric"}

        if semantic_type == "INTEGER":
            if self.is_sparse_count_axis(attr, nums):
                return {"role": "COUNT", "confidence": 0.85, "rationale": "Sparse / zero-inflated discrete distribution"}
            min_val, max_val = min(nums), max(nums)
            if 0 <= min_val and max_val <= 150:
                return {"role": "MEASUREMENT", "subtype": "bounded_quantity", "confidence": 0.75, "rationale": "Bounded integer range"}
            return {"role": "MAGNITUDE", "confidence": 0.7, "rationale": "General integer magnitude"}

        if semantic_type in {"FLOAT", "NUMERIC_GENERAL"}:
            numeric = vsi.get("numeric", {}) or {}
            if numeric.get("is_discrete", False) and self.is_sparse_count_axis(attr, nums):
                return {"role": "COUNT", "confidence": 0.75, "rationale": "Sparse discrete float"}
            min_val, max_val = min(nums), max(nums)
            if 0 <= min_val and max_val <= 1:
                return {"role": "COMPUTATIONAL", "subtype": "normalized", "confidence": 0.75, "rationale": "Normalized [0,1] range"}
            return {"role": "MAGNITUDE", "confidence": 0.65, "rationale": "Continuous numeric magnitude"}

        if any(k in name for k in ["count", "num_", "total_", "cnt"]):
            return {"role": "COUNT", "confidence": 0.7, "rationale": "Name suggests count semantics"}
        if any(k in name for k in ["rate", "ratio", "percent", "pct"]):
            return {"role": "COMPUTATIONAL", "confidence": 0.7, "rationale": "Name suggests derived metric"}
        if any(k in name for k in ["price", "amount", "cost", "salary", "revenue"]):
            return {"role": "MEASUREMENT", "subtype": "monetary", "confidence": 0.75, "rationale": "Name suggests monetary measurement"}

        return None

    # --- total / component detection ---

    def infer_total_component_measures(self, attributes: list) -> dict:
        """Detect TOTAL/COMPONENT numeric relationships.

        Looks for columns whose name implies a total (e.g. ``total_injuries``) and
        whose sample mean ≈ the sum of sibling column means.  Returns a dict with
        ``totals`` (total_name → [component_names]) and ``components``
        (component_name → total_name).
        """
        numeric_types = {"INTEGER", "FLOAT", "NUMERIC_GENERAL", "CURRENCY_AMOUNT"}
        total_hints = {"total", "sum", "all", "combined", "overall"}

        numeric_attrs: list[tuple[str, list[float]]] = []
        for attr in attributes:
            vsi = attr.get("properties", {}).get("value_semantics", {}) or {}
            qvst = attr.get("properties", {}).get("quantitative_vst", {}) or {}
            if (
                vsi.get("semantic_type") in numeric_types
                and qvst.get("role") in {"COUNT", "MEASUREMENT", "MAGNITUDE"}
            ):
                nums = self.get_numeric_samples(attr)
                if nums:
                    numeric_attrs.append((attr["name"], nums))

        if len(numeric_attrs) < 3:
            return {"totals": {}, "components": {}}

        means = {name: sum(nums) / len(nums) for name, nums in numeric_attrs}
        totals: dict[str, list[str]] = {}
        components: dict[str, str] = {}

        for name, _ in numeric_attrs:
            if not any(h in name.lower() for h in total_hints):
                continue
            mean_val = means[name]
            if mean_val <= 0:
                continue

            candidates = [(n, ns) for n, ns in numeric_attrs if n != name]
            found = False
            for size in range(2, min(6, len(candidates) + 1)):
                for combo in combinations(candidates, size):
                    combo_mean = sum(means[n] for n, _ in combo)
                    if abs(combo_mean - mean_val) / (mean_val + 1e-9) < 0.12:
                        comp_names = [n for n, _ in combo]
                        totals[name] = comp_names
                        for cn in comp_names:
                            if cn not in components:
                                components[cn] = name
                        found = True
                        break
                if found:
                    break

        return {"totals": totals, "components": components}

    def infer_safe_aggregation_for_quantitative_vst(self, attr: dict, total_component_info: dict) -> dict | None:
        """Return aggregation safety rules for *attr* given total/component relationships."""
        qvst = attr.get("properties", {}).get("quantitative_vst", {})
        if not qvst:
            return None

        role = qvst.get("role")
        name = attr["name"]
        totals = total_component_info.get("totals", {})
        components = total_component_info.get("components", {})

        result: dict[str, Any] = {
            "can_sum": False,
            "can_avg": False,
            "forbidden_combinations": [],
            "notes": [],
        }

        if name in components:
            total_name = components[name]
            siblings = [c for c in totals.get(total_name, []) if c != name]
            result["can_sum"] = True
            result["can_avg"] = True
            result["forbidden_combinations"] = [total_name] + siblings
            result["notes"].append(f"Component of {total_name} — do not aggregate alongside {total_name} or its siblings")
        elif name in totals:
            result["can_sum"] = True
            result["can_avg"] = False
            result["forbidden_combinations"] = totals[name]
            result["notes"].append(f"Total measure — do not aggregate with components: {totals[name]}")
        elif role == "COUNT":
            result["can_sum"] = True
            result["can_avg"] = False
            result["notes"].append("Count column — SUM is meaningful, AVG is usually misleading")
        elif role == "MEASUREMENT":
            result["can_sum"] = True
            result["can_avg"] = True
        elif role == "COMPUTATIONAL":
            result["can_sum"] = False
            result["can_avg"] = True
            result["notes"].append("Derived/normalized metric — AVG is preferred, do not SUM")
        elif role == "MAGNITUDE":
            result["can_sum"] = True
            result["can_avg"] = True
        else:
            return None

        return result

    def infer_derived_metric_candidates(
        self, attributes: list, process_semantics: dict | None, total_component_info: dict
    ) -> list[dict]:
        """Infer rate / ratio derived metrics suitable for NL2SQL query planning."""
        candidates = []
        entity_keys = (process_semantics or {}).get("entity_keys", [])
        if not entity_keys:
            entity_keys = [
                a["name"] for a in attributes
                if a.get("properties", {}).get("value_semantics", {}).get("is_identifier")
            ]

        components = total_component_info.get("components", {})
        totals = total_component_info.get("totals", {})

        measure_attrs = [
            a for a in attributes
            if a.get("properties", {}).get("quantitative_vst", {}).get("role") in {"MEASUREMENT", "MAGNITUDE"}
        ]

        # Rate candidates: SUM(measure) / COUNT(DISTINCT entity_key)
        if entity_keys and measure_attrs:
            key = entity_keys[0]
            for attr in measure_attrs:
                m = attr["name"]
                if m in components:
                    continue  # use the total instead
                candidates.append({
                    "name": f"{m}_per_event",
                    "type": "RATE",
                    "numerator": m,
                    "denominator": key,
                    "denominator_type": "COUNT_DISTINCT",
                    "formula": f"SUM({m}) / COUNT(DISTINCT {key})",
                    "confidence": 0.7,
                })

        # Share candidates: SUM(component) / SUM(total)
        for total_name, comp_names in totals.items():
            for comp in comp_names:
                candidates.append({
                    "name": f"{comp}_share",
                    "type": "RATIO",
                    "numerator": comp,
                    "denominator": total_name,
                    "formula": f"SUM({comp}) / NULLIF(SUM({total_name}), 0)",
                    "confidence": 0.75,
                })

        return candidates

    # --- process semantics ---

    def identifier_repetition_signal(self, key: str, row_samples: list) -> float:
        counts: dict = {}
        for row in row_samples:
            v = row.get(key)
            if v is None:
                continue
            counts[v] = counts.get(v, 0) + 1
        repeated = sum(1 for c in counts.values() if c >= 2)
        if repeated >= 5:
            return 0.6
        if repeated >= 2:
            return 0.4
        return 0.0

    def temporal_density_signal(self, event_time_attr: str, row_samples: list) -> float:
        times = []
        for row in row_samples:
            v = row.get(event_time_attr)
            if v is None:
                continue
            try:
                times.append(np.datetime64(v))
            except Exception:
                pass
        if len(times) < 10:
            return 0.0
        times = sorted(times)
        deltas = []
        for i in range(1, len(times)):
            delta = float((times[i] - times[i - 1]) / np.timedelta64(1, "D"))
            if delta > 0:
                deltas.append(delta)
        if not deltas:
            return 0.0
        return 0.4 if float(np.mean(deltas)) < 30 else 0.2

    def event_measure_signal(self, attributes: list) -> float:
        count = sum(
            1 for attr in attributes
            if attr.get("properties", {}).get("value_semantics", {}).get("semantic_type")
            in {"INTEGER", "FLOAT", "NUMERIC_GENERAL", "CURRENCY_AMOUNT", "PERCENTAGE", "RATIO"}
        )
        return 0.3 if count >= 2 else (0.15 if count == 1 else 0.0)

    def infer_process_semantics(self, entity_name: str, attributes: list, row_samples: list) -> dict | None:
        if not row_samples or len(row_samples) < 10:
            return None

        entity_keys, event_time_attr = [], None
        fk_id_candidates: list[str] = []  # _id cols that look like foreign keys
        pk_id_candidates: list[str] = []  # _id col that matches the table's own PK name
        _time_keywords = {"date", "_at", "time", "timestamp", "when", "created", "updated"}
        entity_lower = entity_name.lower()
        for attr in attributes:
            name = attr["name"]
            name_lower = name.lower()
            vsi = attr.get("properties", {}).get("value_semantics", {})
            role = attr.get("properties", {}).get("semantic_role", {})
            if vsi.get("is_identifier"):
                entity_keys.append(name)
            elif name_lower.endswith("_id"):
                # Prefer FK-like _id columns (account_id, client_id) over the
                # table's own PK (trans_id, loan_id) as the process entity key.
                if name_lower == f"{entity_lower}_id":
                    pk_id_candidates.append(name)
                else:
                    fk_id_candidates.append(name)
            if not event_time_attr:
                # VSI-based (set by base-layer SemanticTypeInferencer)
                if role.get("primary_role") == "EVENT_TIME" or vsi.get("semantic_type") in {"DATE", "DATETIME", "TIME"}:
                    event_time_attr = name
                # name-based fallback when VSI not yet available
                elif any(kw in name_lower for kw in _time_keywords):
                    event_time_attr = name

        if not entity_keys:
            entity_keys = fk_id_candidates or pk_id_candidates

        if not event_time_attr:
            return None

        key = entity_keys[0] if entity_keys else None
        repetition_score = self.identifier_repetition_signal(key, row_samples) if key else 0.0
        temporal_score = self.temporal_density_signal(event_time_attr, row_samples)
        measure_score = self.event_measure_signal(attributes)
        process_score = repetition_score + temporal_score + measure_score

        if process_score < 0.5:
            return None

        event_mode = "SEQUENCE_EVENT" if repetition_score >= 0.4 else "ATOMIC_EVENT"
        return {
            "row_semantics": "EVENT",
            "event_mode": event_mode,
            "entity_keys": entity_keys,
            "event_time": event_time_attr,
            "signals": {
                "identifier_repetition": repetition_score,
                "temporal_density": temporal_score,
                "event_measure_presence": measure_score,
            },
            "constraints": {
                "requires_aggregation": True,
                "requires_temporal_reasoning": True,
                "row_local_substitution_invalid": True,
            },
            "confidence": round(process_score, 2),
            "rationale": "Multiple structural signals indicate rows represent events.",
        }

    def infer_attribute_process_roles(self, attributes: list, process_semantics: dict) -> dict[str, dict]:
        roles: dict[str, dict] = {}
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        for attr in attributes:
            name = attr["name"]
            vsi = attr.get("properties", {}).get("value_semantics", {}) or {}
            role = attr.get("properties", {}).get("semantic_role", {}) or {}
            if name == event_time:
                roles[name] = {"process_vst_role": "EVENT_TIME", "confidence": 0.95, "rationale": "Event timestamp."}
                continue
            if name in entity_keys:
                roles[name] = {"process_vst_role": "PROCESS_KEY", "confidence": 0.95, "rationale": "Entity identifier for event sequences."}
                continue
            semantic_type = vsi.get("semantic_type")
            if semantic_type in {"INTEGER", "FLOAT", "NUMERIC_GENERAL"} and role.get("primary_role") == "EVIDENCE":
                roles[name] = {"process_vst_role": "STATE_VARIABLE", "confidence": 0.6, "rationale": "Evolving state."}
            elif semantic_type in {"CURRENCY_AMOUNT", "INTEGER", "FLOAT", "NUMERIC_GENERAL", "PERCENTAGE", "RATIO"}:
                roles[name] = {"process_vst_role": "EVENT_MEASURE", "confidence": 0.7, "rationale": "Numeric measurement at event."}
        return roles

    def infer_process_patterns(self, entity_name: str, attributes: list, row_samples: list, process_semantics: dict) -> dict | None:
        if not process_semantics:
            return None
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        if not event_time or not entity_keys:
            return None

        key = entity_keys[0]
        sequences: dict = {}
        for row in row_samples:
            k = row.get(key)
            t = row.get(event_time)
            if k is None or t is None:
                continue
            try:
                sequences.setdefault(k, []).append(np.datetime64(t))
            except Exception:
                pass

        if len(sequences) < 3 or sum(1 for s in sequences.values() if len(s) >= 3) < 3:
            return None

        intervals = []
        for seq in sequences.values():
            if len(seq) < 3:
                continue
            for i in range(1, len(sorted(seq))):
                delta = float((sorted(seq)[i] - sorted(seq)[i - 1]) / np.timedelta64(1, "D"))
                if delta > 0:
                    intervals.append(delta)

        if len(intervals) < 10:
            return None

        mean_i = float(np.mean(intervals))
        std_i = float(np.std(intervals))
        cadence = "irregular"
        if abs(mean_i - 30) < 5:
            cadence = "monthly"
        elif abs(mean_i - 7) < 2:
            cadence = "weekly"
        elif abs(mean_i - 1) < 0.5:
            cadence = "daily"

        return {
            "entity_key": key,
            "event_time": event_time,
            "expected_interval_days": round(mean_i, 2),
            "interval_variance": round(std_i, 2),
            "cadence": cadence,
            "irregularity_threshold": round(std_i * 2, 2),
            "confidence": 0.7,
            "rationale": "Stable temporal cadence detected across event sequences.",
        }

    def infer_temporal_trends(self, attributes: list, row_samples: list, process_semantics: dict) -> dict | None:
        if not process_semantics:
            return None
        event_time = process_semantics.get("event_time")
        if not event_time:
            return None

        measure_types = {"INTEGER", "FLOAT", "NUMERIC_GENERAL", "CURRENCY_AMOUNT", "PERCENTAGE", "RATIO"}
        event_measures = [
            attr["name"] for attr in attributes
            if attr.get("properties", {}).get("value_semantics", {}).get("semantic_type") in measure_types
        ]
        if not event_measures:
            return None

        trends = []
        for measure in event_measures:
            t_vals, v_vals = [], []
            for row in row_samples:
                t, v = row.get(event_time), row.get(measure)
                if t is None or v is None:
                    continue
                try:
                    t_vals.append(int(np.datetime64(t).astype("datetime64[D]").astype(int)))
                    v_vals.append(float(v))
                except Exception:
                    pass
            if len(t_vals) < 10:
                continue
            idx = np.argsort(t_vals)
            t_norm = np.array(t_vals)[idx] - min(t_vals)
            v_sorted = np.array(v_vals)[idx]
            try:
                slope = float(np.polyfit(t_norm, v_sorted, 1)[0])
            except Exception:
                continue
            direction = "stable"
            if slope > 0.01:
                direction = "increasing"
            elif slope < -0.01:
                direction = "decreasing"
            trends.append({"measure": measure, "trend_direction": direction, "slope": round(slope, 4), "confidence": 0.7, "rationale": "Temporal regression over ordered measurements"})

        return {"event_time": event_time, "trends": trends, "confidence": 0.7} if trends else None

    def infer_conditional_distributions(self, group_attr: dict, value_attr: dict, row_samples: list) -> dict | None:
        g_name, v_name = group_attr["name"], value_attr["name"]
        groups: dict = {}
        for row in row_samples:
            g, v = row.get(g_name), row.get(v_name)
            if g is None or v is None:
                continue
            try:
                groups.setdefault(g, []).append(float(v))
            except Exception:
                pass

        profiles = {}
        for g, vals in groups.items():
            if len(vals) < 10:
                continue
            profiles[str(g)] = {
                "count": len(vals),
                "p50": round(float(np.percentile(vals, 50)), 2),
                "p90": round(float(np.percentile(vals, 90)), 2),
                "p99": round(float(np.percentile(vals, 99)), 2),
                "typical_range": [round(float(np.min(vals)), 2), round(float(np.percentile(vals, 90)), 2)],
                "extreme_range": [round(float(np.percentile(vals, 90)), 2), round(float(np.max(vals)), 2)],
            }

        if len(profiles) < 2 or len(profiles) > 10:
            return None

        return {
            "group_attribute": g_name,
            "value_attribute": v_name,
            "profiles": profiles,
            "recommended_stat": "p99",
            "confidence": 0.7,
            "rationale": "Conditional distributions from row-aligned numeric behavior",
        }

    # --- process operator semantics ---

    def get_process_numeric_measures(self, attributes: list, process_semantics: dict) -> list[dict]:
        """Return numeric measure attributes that are not entity keys or the event time."""
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        measure_types = {"INTEGER", "FLOAT", "NUMERIC_GENERAL", "CURRENCY_AMOUNT", "PERCENTAGE", "RATIO"}
        return [
            a for a in attributes
            if a["name"] not in entity_keys
            and a["name"] != event_time
            and a.get("properties", {}).get("value_semantics", {}).get("semantic_type") in measure_types
        ]

    def get_state_variable_candidates(self, attributes: list, process_semantics: dict) -> list[dict]:
        """Return attributes classified as STATE_VARIABLE in process VST roles."""
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        return [
            a for a in attributes
            if a["name"] not in entity_keys
            and a["name"] != event_time
            and a.get("properties", {}).get("process_vst_role", {}).get("process_vst_role") == "STATE_VARIABLE"
        ]

    def infer_process_mode(self, process_semantics: dict | None) -> str | None:
        """Classify event mode from computed process_semantics signals."""
        if not process_semantics:
            return None
        signals = process_semantics.get("signals", {})
        repetition = signals.get("identifier_repetition", 0.0)
        temporal = signals.get("temporal_density", 0.0)
        if repetition >= 0.4:
            return "SEQUENCE_EVENT"
        if temporal >= 0.4:
            return "REPEATED_EVENT"
        return "ATOMIC_EVENT"

    def infer_time_grain_candidates(self, event_time_attr: str, row_samples: list) -> list[str]:
        """Infer appropriate time bucketing granularities from timestamp distribution."""
        times = []
        for row in row_samples:
            v = row.get(event_time_attr)
            if v is None:
                continue
            try:
                times.append(np.datetime64(v))
            except Exception:
                pass

        if len(times) < 10:
            return []

        times_sorted = sorted(times)
        deltas = []
        for i in range(1, len(times_sorted)):
            delta = float((times_sorted[i] - times_sorted[i - 1]) / np.timedelta64(1, "D"))
            if delta > 0:
                deltas.append(delta)

        if not deltas:
            return []

        mean_delta = float(np.mean(deltas))
        if mean_delta <= 1.5:
            return ["hourly", "daily"]
        if mean_delta <= 7.5:
            return ["daily", "weekly"]
        if mean_delta <= 35:
            return ["weekly", "monthly"]
        return ["monthly", "quarterly"]

    def infer_process_operator_semantics(self, attributes: list, process_semantics: dict) -> list[dict]:
        """Derive NL2SQL operators from process semantics (AGGREGATE_OVER_TIME, CHANGE_DETECTION, etc.)."""
        operators = []
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        event_mode = process_semantics.get("event_mode", "ATOMIC_EVENT")

        numeric_measures = self.get_process_numeric_measures(attributes, process_semantics)
        state_vars = self.get_state_variable_candidates(attributes, process_semantics)

        if event_time and numeric_measures:
            operators.append({
                "operator": "AGGREGATE_OVER_TIME",
                "event_time": event_time,
                "measures": [a["name"] for a in numeric_measures],
                "confidence": 0.8,
                "rationale": "Temporal event with numeric measures enables time-series aggregation",
            })

        if event_mode in ("REPEATED_EVENT", "SEQUENCE_EVENT") and entity_keys and numeric_measures:
            operators.append({
                "operator": "CHANGE_DETECTION",
                "entity_keys": entity_keys,
                "event_time": event_time,
                "measures": [a["name"] for a in numeric_measures],
                "confidence": 0.7,
                "rationale": "Repeated events per entity enable change-over-time queries",
            })

        if state_vars and entity_keys:
            operators.append({
                "operator": "CURRENT_STATE",
                "entity_keys": entity_keys,
                "state_variables": [a["name"] for a in state_vars],
                "event_time": event_time,
                "confidence": 0.75,
                "rationale": "State variables imply latest-state-per-entity queries",
            })

        count_measures = [
            a for a in numeric_measures
            if a.get("properties", {}).get("quantitative_vst", {}).get("role") == "COUNT"
        ]
        raw_measures = [
            a for a in numeric_measures
            if a.get("properties", {}).get("quantitative_vst", {}).get("role") in {"MEASUREMENT", "MAGNITUDE"}
        ]
        if count_measures and raw_measures:
            operators.append({
                "operator": "NORMALIZED_RATE",
                "numerator_measures": [a["name"] for a in raw_measures],
                "denominator_counts": [a["name"] for a in count_measures],
                "confidence": 0.65,
                "rationale": "Mixed count and measurement columns suggest rate normalization",
            })

        return operators

    def infer_process_query_constraints(self, operators: list, process_semantics: dict) -> dict:
        """Generate query planner constraints from process operators and semantics."""
        constraints: dict[str, Any] = {}
        event_time = process_semantics.get("event_time")
        entity_keys = process_semantics.get("entity_keys", [])
        op_types = {op["operator"] for op in operators}

        if "AGGREGATE_OVER_TIME" in op_types and event_time:
            constraints["requires_time_filter"] = {
                "field": event_time,
                "reason": "Time-series queries should be bounded to avoid full scans",
            }

        if "CHANGE_DETECTION" in op_types and entity_keys:
            constraints["requires_entity_key_filter"] = {
                "fields": entity_keys,
                "reason": "Change detection queries need to scope to specific entities",
            }

        if "CURRENT_STATE" in op_types and event_time and entity_keys:
            constraints["latest_record_only"] = {
                "order_by": event_time,
                "partition_by": entity_keys,
                "reason": "State queries should return the most recent record per entity",
            }

        if process_semantics.get("constraints", {}).get("requires_aggregation"):
            constraints["no_row_local_substitution"] = True

        return constraints

    def infer_role_query_constraints(self, attributes: list, semantic_links: list) -> dict[str, dict]:
        """Derive per-attribute query planning constraints from semantic roles and safe aggregation."""
        constraints: dict[str, dict] = {}

        for attr in attributes:
            name = attr["name"]
            role = (attr.get("properties", {}).get("semantic_role") or {})
            safe_agg = (attr.get("properties", {}).get("safe_aggregation") or {})
            primary_role = role.get("primary_role")

            con: dict[str, Any] = {}

            if primary_role == "IDENTIFIER":
                con["can_group_by"] = True
                con["can_filter"] = True
                con["should_not_aggregate"] = True
            elif primary_role == "SEGMENTATION_DRIVER":
                con["can_group_by"] = True
                con["can_filter"] = True
            elif primary_role == "EVENT_TIME":
                con["can_order_by"] = True
                con["can_filter"] = True
                con["can_group_by"] = True
            elif primary_role == "EVIDENCE":
                con["can_aggregate"] = True

            if safe_agg:
                if not safe_agg.get("can_sum", True):
                    con["should_not_sum"] = True
                if safe_agg.get("forbidden_combinations"):
                    con["forbidden_combinations"] = safe_agg["forbidden_combinations"]

            if con:
                constraints[name] = con

        return constraints

    # ------------------------------------------------------------------
    # Top-level collection enrichment methods
    # ------------------------------------------------------------------

    def _write_entity_and_attribute_descriptions(self, data_registry, source, database, collection, entity_name, parsed, rebuild):
        table_desc = parsed.get("table_description", "")
        attribute_descs = parsed.get("attributes", {})

        if self.properties.get("enable_entity_description_generation", True):
            current = data_registry.get_source_database_collection_entity_description(source, database, collection, entity_name)
            if not current or current.strip() == "" or rebuild:
                data_registry.set_source_database_collection_entity_description(source, database, collection, entity_name, table_desc, rebuild=rebuild)

        if self.properties.get("enable_attribute_description_generation", True):
            for attr, desc in attribute_descs.items():
                current = data_registry.get_source_database_collection_entity_attribute_description(source, database, collection, entity_name, attr)
                if not current or current.strip() == "" or rebuild:
                    data_registry.set_source_database_collection_entity_attribute_description(source, database, collection, entity_name, attr, desc, rebuild=rebuild)

        return table_desc

    def enrich_entity_metadata(self, data_registry, source, database, collection, entity, attributes, rebuild):
        """Generate and write LLM descriptions for an entity and all its attributes.

        Skips writing when a description already exists and ``rebuild`` is ``False``.
        """
        entity_name = entity.get("name")
        if not rebuild:
            existing = data_registry.get_source_database_collection_entity_description(source, database, collection, entity_name)
            if existing and existing.strip():
                return existing
        raw = self.enrich_entity(entity, attributes)
        if raw is None:
            return None
        try:
            parsed = safe_json_parse(raw)
            if not parsed:
                return None
        except Exception:
            return None
        return self._write_entity_and_attribute_descriptions(data_registry, source, database, collection, entity_name, parsed, rebuild)

    def enrich_attributes(self, data_registry, source, database, collection, entity_name, attributes, rebuild):
        """Run per-attribute enrichment: VSI, SDI, DCM, IVS, quantitative VST, total/component, and safe aggregation.

        Writes results directly into the registry. Returns the refreshed attribute
        list (re-fetched after each stage so later stages see earlier results).
        Attributes without stats are skipped for LLM-based steps.
        """
        # VSI + SDI
        for attr in attributes:
            attr_name = attr.get("name")
            if not attr.get("properties", {}).get("stats"):
                continue

            if self.properties.get("enable_value_semantics_inference", True):
                existing = data_registry.get_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "value_semantics")
                if not existing or rebuild:
                    vsi = self.infer_attribute_vsi(entity_name, attr)
                    if vsi:
                        data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "value_semantics", vsi, rebuild=rebuild)

            if self.properties.get("enable_semantic_discovery_inference", True):
                existing_sdi = data_registry.get_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "semantic_discovery")
                if not existing_sdi or rebuild:
                    sdi = self.infer_attribute_sdi(entity_name, attr)
                    if sdi:
                        data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "semantic_discovery", sdi, rebuild=rebuild)

        # refresh
        attributes = data_registry.list_entity_attributes(source, database, collection, entity_name)

        # DCM
        if self.properties.get("enable_domain_concept_mapping", True):
            for attr in attributes:
                attr_name = attr.get("name")
                if "value_semantics" not in attr.get("properties", {}):
                    continue
                existing = data_registry.get_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "domain_concept")
                if not existing or rebuild:
                    dcm = self.infer_domain_concept(entity_name, attr)
                    if dcm:
                        data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "domain_concept", dcm, rebuild=rebuild)

        # IVS
        if self.properties.get("enable_interpretive_semantics", True):
            for attr in attributes:
                ivs = self.infer_interpretive_semantics(entity_name, attr)
                if ivs:
                    data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr["name"], "interpretive_semantics", ivs, rebuild=rebuild)

        # Quantitative VST
        if self.properties.get("enable_quantitative_semantics_inference", True):
            for attr in attributes:
                qvst = self.infer_quantitative_vst_role(attr)
                if qvst:
                    data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr["name"], "quantitative_vst", qvst, rebuild=rebuild)

        # Total/Component detection + Safe Aggregation
        if (
            self.properties.get("enable_total_component_detection", True)
            or self.properties.get("enable_safe_aggregation_inference", True)
        ):
            # refresh so quantitative_vst is visible
            attributes = data_registry.list_entity_attributes(source, database, collection, entity_name)
            tc_info: dict = {"totals": {}, "components": {}}

            if self.properties.get("enable_total_component_detection", True):
                tc_info = self.infer_total_component_measures(attributes)
                if tc_info["totals"] or tc_info["components"]:
                    data_registry.set_source_database_collection_entity_property(
                        source, database, collection, entity_name,
                        "total_component_measures", tc_info, rebuild=rebuild,
                    )

            if self.properties.get("enable_safe_aggregation_inference", True):
                for attr in attributes:
                    safe_agg = self.infer_safe_aggregation_for_quantitative_vst(attr, tc_info)
                    if safe_agg:
                        data_registry.set_source_database_collection_entity_attribute_property(
                            source, database, collection, entity_name,
                            attr["name"], "safe_aggregation", safe_agg, rebuild=rebuild,
                        )

        return attributes

    def enrich_relations(self, data_registry, source, database, collection, entity_name, attributes, row_samples, rebuild):
        """Infer and write cross-attribute relationships: value axes, semantic links, roles, query constraints, and conditional distributions.

        Semantic links are cached in the registry when ``rebuild=False`` to avoid
        redundant LLM calls on subsequent passes.
        """
        # Value Axis
        if self.properties.get("enable_value_axis_inference", True):
            axes = self.infer_value_axis(attributes, row_samples)
            for attr_name, axis in axes.items():
                data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "value_axis", axis, rebuild=rebuild)

        # Semantic Links + Roles + CDS
        if self.properties.get("enable_semantic_links_inference", True):
            # Re-use stored links when rebuild=False — validate_semantic_link calls
            # the LLM for every candidate pair, so skipping it on subsequent passes
            # is critical for idempotency.
            cached_links = None if rebuild else data_registry.get_source_database_collection_entity_property(
                source, database, collection, entity_name, "semantic_links"
            )

            if cached_links is not None:
                validated_links = cached_links
            else:
                semantic_links = self.infer_semantic_links(attributes)
                row_links = self.infer_row_based_links(attributes, row_samples)
                for l in row_links:
                    l["row_support"] = True
                semantic_links += row_links

                validated_links = []
                for link in semantic_links:
                    try:
                        src = next(a for a in attributes if a["name"] == link["source"])
                        tgt = next(a for a in attributes if a["name"] == link["target"])
                    except StopIteration:
                        continue

                    # pre-filter: statistical signal must pass before calling LLM
                    if not self.validate_relational_link_signal(src, tgt, link["signal"], row_samples):
                        continue

                    result = self.validate_semantic_link(src, tgt, link["signal"])
                    relationship = result.get("relationship") if result else None

                    # fall back to deterministic assignment when LLM is absent
                    if relationship is None:
                        signal_type = link["signal"].get("type") if isinstance(link["signal"], dict) else link["signal"]
                        relationship = {
                            "grouped_distribution": "SEGMENTS",
                            "functional_dependency": "DERIVES",
                            "temporal_alignment": "SUPPORTS",
                        }.get(signal_type)

                    if relationship and relationship != "UNRELATED":
                        confidence = result.get("confidence", 0.6) if result else 0.6
                        if link.get("row_support"):
                            confidence = max(0.7, confidence)
                        validated_links.append({
                            "source": link["source"],
                            "target": link["target"],
                            "relationship": relationship,
                            "confidence": confidence,
                            "rationale": result.get("rationale") if result else "Structure-backed semantic signal",
                        })

                if validated_links:
                    data_registry.set_source_database_collection_entity_property(source, database, collection, entity_name, "semantic_links", validated_links, rebuild=rebuild)

            # Semantic roles
            for attr in attributes:
                role = self.infer_semantic_role(attr, attributes, validated_links)
                if role:
                    data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr["name"], "semantic_role", role, rebuild=rebuild)

            # Role-based query constraints
            if self.properties.get("enable_role_query_constraints", True):
                refreshed = data_registry.list_entity_attributes(source, database, collection, entity_name)
                role_constraints = self.infer_role_query_constraints(refreshed, validated_links)
                for attr_name, con in role_constraints.items():
                    data_registry.set_source_database_collection_entity_attribute_property(
                        source, database, collection, entity_name,
                        attr_name, "role_query_constraints", con, rebuild=rebuild,
                    )

            # Conditional distributions (SEGMENTS links only)
            if validated_links and row_samples:
                for link in validated_links:
                    if link.get("relationship") != "SEGMENTS":
                        continue
                    try:
                        g_attr = next(a for a in attributes if a["name"] == link["source"])
                        v_attr = next(a for a in attributes if a["name"] == link["target"])
                    except StopIteration:
                        continue

                    g_role = g_attr.get("properties", {}).get("semantic_role", {})
                    if g_role.get("primary_role") != "SEGMENTATION_DRIVER":
                        continue

                    v_type = v_attr.get("properties", {}).get("value_semantics", {}).get("semantic_type")
                    if v_type not in {"CURRENCY_AMOUNT", "INTEGER", "FLOAT", "NUMERIC_GENERAL", "PERCENTAGE", "RATIO", "DURATION"}:
                        continue

                    cds = self.infer_conditional_distributions(g_attr, v_attr, row_samples)
                    if cds:
                        existing = data_registry.get_source_database_collection_entity_attribute_property(source, database, collection, entity_name, v_attr["name"], "conditional_value_distribution") or {}
                        existing[g_attr["name"]] = cds
                        data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, v_attr["name"], "conditional_value_distribution", existing, rebuild=rebuild)

        return attributes

    def enrich_process_semantics(self, data_registry, source, database, collection, entity_name, attributes, row_samples, rebuild):
        """Detect event-table semantics and write process-level properties to the registry.

        Writes: ``process_semantics``, ``process_patterns``, ``process_trends``,
        ``process_operators``, ``process_query_constraints``, ``time_grain_candidates``
        (on the event-time attribute), ``derived_metric_candidates``, and per-attribute
        ``process_vst_role``. No-ops when the entity does not qualify as an event table.
        """
        if not self.properties.get("enable_process_semantics_inference", True):
            return
        ps = self.infer_process_semantics(entity_name, attributes, row_samples)
        if not ps:
            return

        data_registry.set_source_database_collection_entity_property(source, database, collection, entity_name, "process_semantics", ps, rebuild=rebuild)

        roles = self.infer_attribute_process_roles(attributes, ps)
        for attr_name, role in roles.items():
            data_registry.set_source_database_collection_entity_attribute_property(source, database, collection, entity_name, attr_name, "process_vst_role", role, rebuild=rebuild)

        patterns = self.infer_process_patterns(entity_name, attributes, row_samples, ps)
        if patterns:
            data_registry.set_source_database_collection_entity_property(source, database, collection, entity_name, "process_patterns", patterns, rebuild=rebuild)

        trends = self.infer_temporal_trends(attributes, row_samples, ps)
        if trends:
            data_registry.set_source_database_collection_entity_property(source, database, collection, entity_name, "process_trends", trends, rebuild=rebuild)

        if not self.properties.get("enable_process_operator_semantics", True):
            return

        # Refine event_mode using dedicated signal analysis
        refined_mode = self.infer_process_mode(ps)
        if refined_mode and refined_mode != ps.get("event_mode"):
            ps["event_mode"] = refined_mode
            data_registry.set_source_database_collection_entity_property(
                source, database, collection, entity_name, "process_semantics", ps, rebuild=rebuild,
            )

        # refresh attributes so safe_aggregation / quantitative_vst are populated
        attributes = data_registry.list_entity_attributes(source, database, collection, entity_name)

        operators = self.infer_process_operator_semantics(attributes, ps)
        if operators:
            data_registry.set_source_database_collection_entity_property(
                source, database, collection, entity_name, "process_operators", operators, rebuild=rebuild,
            )

        event_time = ps.get("event_time")
        if event_time and row_samples:
            grains = self.infer_time_grain_candidates(event_time, row_samples)
            if grains:
                data_registry.set_source_database_collection_entity_attribute_property(
                    source, database, collection, entity_name,
                    event_time, "time_grain_candidates", grains, rebuild=rebuild,
                )

        constraints = self.infer_process_query_constraints(operators, ps)
        if constraints:
            data_registry.set_source_database_collection_entity_property(
                source, database, collection, entity_name, "process_query_constraints", constraints, rebuild=rebuild,
            )

        if self.properties.get("enable_derived_metric_candidates", True):
            tc_info = data_registry.get_source_database_collection_entity_property(
                source, database, collection, entity_name, "total_component_measures",
            ) or {"totals": {}, "components": {}}
            derived = self.infer_derived_metric_candidates(attributes, ps, tc_info)
            if derived:
                data_registry.set_source_database_collection_entity_property(
                    source, database, collection, entity_name, "derived_metric_candidates", derived, rebuild=rebuild,
                )

    def enrich_entity_full(self, data_registry, source, database, collection, entity, attributes, rebuild=False):
        """Run the full enrichment pipeline for a single entity."""
        entity_name = entity.get("name")
        entity_stats = entity.get("properties", {}).get("stats", {})
        row_samples = entity_stats.get("row_samples", [])

        self.current_entity_row_samples = row_samples
        self.current_entity_attributes = attributes

        self.enrich_entity_metadata(data_registry, source, database, collection, entity, attributes, rebuild)
        attributes = self.enrich_attributes(data_registry, source, database, collection, entity_name, attributes, rebuild)
        attributes = self.enrich_relations(data_registry, source, database, collection, entity_name, attributes, row_samples, rebuild)
        self.enrich_process_semantics(data_registry, source, database, collection, entity_name, attributes, row_samples, rebuild)

    # ------------------------------------------------------------------
    # Source-level entry points (mirror the original collect_source_* API)
    # ------------------------------------------------------------------

    def collect_source_database_collection_metadata(self, data_registry, source, database, collection, recursive=False, rebuild=False):
        """Run full enrichment for every entity in a collection, then generate the collection-level description."""
        entities = data_registry.list_collection_entities(source, database, collection)
        entity_descriptions = {}

        for entity in entities:
            entity_name = entity.get("name")
            attributes = data_registry.list_entity_attributes(source, database, collection, entity_name)
            entity_stats = entity.get("properties", {}).get("stats", {})
            row_samples = entity_stats.get("row_samples", [])

            self.enrich_entity_full(data_registry, source, database, collection, entity, attributes, rebuild)

            # collect entity description for collection-level aggregation
            desc = data_registry.get_source_database_collection_entity_description(source, database, collection, entity_name)
            entity_descriptions[entity_name] = desc

        if self.properties.get("enable_collection_description_generation", True):
            current = data_registry.get_source_database_collection_description(source, database, collection)
            if not current or current.strip() == "" or rebuild:
                meta = data_registry.get_source_database_collection_property(source, database, collection, "metadata") or {"name": collection, "type": "collection"}
                desc = self.enrich_collection_description(collection, entity_descriptions, meta)
                if desc:
                    data_registry.set_source_database_collection_description(source, database, collection, desc, rebuild=rebuild)

    def collect_source_database_metadata(self, data_registry, source, database, recursive=False, rebuild=False):
        """Enrich all collections in a database (when recursive) and generate the database-level description."""
        collections = data_registry.list_database_collections(source, database)
        collection_descriptions = {}

        if recursive:
            for coll in collections:
                coll_name = coll.get("name")
                self.collect_source_database_collection_metadata(data_registry, source, database, coll_name, recursive=True, rebuild=rebuild)

        if self.properties.get("enable_database_description_generation", True):
            current = data_registry.get_source_database_description(source, database)
            if not current or current.strip() == "" or rebuild:
                meta = data_registry.get_source_database_property(source, database, "metadata") or {"name": database, "type": "database"}
                for coll in collections:
                    coll_name = coll.get("name")
                    collection_descriptions[coll_name] = coll.get("description")
                desc = self.enrich_database_description(database, collection_descriptions, meta)
                if desc:
                    data_registry.set_source_database_description(source, database, desc, rebuild=rebuild)

    def collect_source_metadata(self, data_registry, source, recursive=False, rebuild=False):
        """Top-level entry point. Call from DataRegistry.enrich_source_metadata()."""
        databases = data_registry.list_source_databases(source)
        for db in databases:
            self.collect_source_database_metadata(data_registry, source, db.get("name"), recursive=recursive, rebuild=rebuild)
