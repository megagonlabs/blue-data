import os

from fastapi import HTTPException, Request

from blue_data.registry.data_registry import DataRegistry
from registry_api.config import get_registry as _get_registry

_OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


def get_registry() -> DataRegistry:
    """FastAPI dependency — override in tests via app.dependency_overrides."""
    return _get_registry()


def writes_enabled() -> bool:
    return os.environ.get("BLUE_DATA_API_ALLOW_WRITES", "").lower() in ("1", "true", "yes")


def require_api_key(request: Request) -> None:
    """App-wide auth. Enforced only when BLUE_DATA_API_KEY is set; otherwise
    auth is disabled (a warning is logged at startup). Accepts the key via the
    X-API-Key header or an Authorization: Bearer token. /health and the docs
    routes are always open."""
    expected = os.environ.get("BLUE_DATA_API_KEY")
    if not expected or request.url.path in _OPEN_PATHS:
        return
    provided = request.headers.get("x-api-key")
    if not provided:
        auth = request.headers.get("authorization", "")
        if auth[:7].lower() == "bearer ":
            provided = auth[7:].strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
