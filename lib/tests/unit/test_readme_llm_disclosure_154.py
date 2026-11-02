"""Regression guard for issue #154 (disclose LLM cost/model in the READMEs).

The scored scenario demos generate SQL live with a default LLM, so the advertised
baseline/enriched numbers are model- and run-dependent. The READMEs must (a) disclose the
exact default model the demos use, and (b) make clear those scores come from live NL->SQL
(an LLM call), not from the deterministic "zero LLM cost" enrichment. This pins the model
string in sync with the demos so it can't silently drift.
"""
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_CODED_VALUE_DEMO = _REPO / "examples" / "scenario-demos" / "coded_value_demo.py"
_ROOT_README = _REPO / "README.md"
_EXAMPLES_README = _REPO / "examples" / "README.md"


def _demo_default_model() -> str:
    text = _CODED_VALUE_DEMO.read_text()
    m = re.search(r'BLUE_DATA_LLM_MODEL["\']\s*,\s*["\']([^"\']+)["\']', text)
    assert m, "could not find the demo's default BLUE_DATA_LLM_MODEL"
    return m.group(1)


def test_readmes_disclose_the_demo_default_model():
    model = _demo_default_model()
    assert model in _EXAMPLES_README.read_text(), f"examples/README must name the demo model {model!r}"
    assert model in _ROOT_README.read_text(), f"README must name the demo model {model!r}"


def test_examples_readme_flags_scores_as_live_nl2sql():
    text = _EXAMPLES_README.read_text().lower()
    # The disclosure must tie the scores to a live LLM call and flag run/model variance.
    assert "nl" in text and "sql" in text
    assert "model- and run-dependent" in text or "vary by model" in text


def test_root_readme_separates_free_from_llm_paths():
    text = _ROOT_README.read_text().lower()
    assert "no api key" in text or "no per-call cost" in text
    assert "do** call an llm" in text or "call an llm" in text
