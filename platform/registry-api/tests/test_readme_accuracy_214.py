"""Regression guard for issue #214 (registry-api README omitted auth variables).

The README's env table never mentioned the API-auth/bind/writes variables the code
reads, so every documented curl in "Typical workflow" returned 401. Keep the README
documenting each BLUE_DATA_API_* variable the service honors.
"""
from pathlib import Path

_README = Path(__file__).resolve().parents[1] / "README.md"

# The BLUE_DATA_API_* variables the service reads (server.py / deps.py).
_API_VARS = [
    "BLUE_DATA_API_KEY",
    "BLUE_DATA_API_AUTH_DISABLED",
    "BLUE_DATA_API_HOST",
    "BLUE_DATA_API_PORT",
    "BLUE_DATA_API_ALLOW_WRITES",
]


def test_readme_documents_api_variables():
    text = _README.read_text()
    missing = [v for v in _API_VARS if v not in text]
    assert not missing, f"registry-api README is missing: {missing}"


def test_readme_shows_how_to_authenticate():
    text = _README.read_text()
    # The two header forms the key guard accepts.
    assert "X-API-Key" in text
    assert "Bearer" in text
