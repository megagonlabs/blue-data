import os

from fastapi import HTTPException, Request

from blue_data.registry.data_registry import DataRegistry
from registry_api.config import get_registry as _get_registry

_OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_SIMPLE_CONTENT_TYPES = {
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
}


def get_registry() -> DataRegistry:
    """FastAPI dependency — override in tests via app.dependency_overrides."""
    return _get_registry()


def writes_enabled() -> bool:
    return os.environ.get("BLUE_DATA_API_ALLOW_WRITES", "").lower() in ("1", "true", "yes")


def auth_disabled() -> bool:
    return os.environ.get("BLUE_DATA_API_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


def require_api_key(request: Request) -> None:
    """App-wide auth, mandatory by default. Clients present the key via the
    X-API-Key header or an Authorization: Bearer token. When BLUE_DATA_API_KEY is
    unset, every data endpoint is refused unless BLUE_DATA_API_AUTH_DISABLED is set
    (an explicit, logged opt-out). /health and the docs routes are always open."""
    if request.url.path in _OPEN_PATHS:
        return
    expected = os.environ.get("BLUE_DATA_API_KEY")
    if not expected:
        if auth_disabled():
            return
        raise HTTPException(
            status_code=401,
            detail="API key required. Set BLUE_DATA_API_KEY, or "
                   "BLUE_DATA_API_AUTH_DISABLED=true to run without auth.",
        )
    provided = request.headers.get("x-api-key")
    if not provided:
        auth = request.headers.get("authorization", "")
        if auth[:7].lower() == "bearer ":
            provided = auth[7:].strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_safe_content_type(request: Request) -> None:
    """CSRF mitigation: reject state-changing requests carrying a browser-simple
    content type (form/multipart/text) that a cross-site HTML form could forge.
    API clients use application/json (or send no body), which is unaffected."""
    if request.method not in _STATE_CHANGING_METHODS or request.url.path in _OPEN_PATHS:
        return
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type in _CSRF_SIMPLE_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="State-changing requests must use application/json (CSRF protection).",
        )
