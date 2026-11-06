"""Shared FastAPI server helpers for blue-data platform services.

One place for the family-wide HTTP policy so every service (registry / doc / web /
user APIs, ops-mcp) binds and authenticates the same way:

- loopback by default; host/port from the environment
- API key mandatory by default, with an explicit opt-out
- a JSON content-type requirement on state-changing routes (CSRF protection)

Each service picks its own env prefix and default port, e.g.::

    from blue_data.server import resolve_bind, security_dependencies
    app = FastAPI(dependencies=security_dependencies("BLUE_DOC_API"))
    host, port = resolve_bind("BLUE_DOC_API", default_port=8001)

Requires fastapi (installed by the API service packages); core blue-data never
imports this module.
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

DEFAULT_OPEN_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CSRF_SIMPLE_CONTENT_TYPES = frozenset({
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
})


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def resolve_bind(prefix: str = "BLUE_DATA_API", default_port: int = 8000) -> tuple[str, int]:
    """Return (host, port) from ``{prefix}_HOST`` / ``{prefix}_PORT``; defaults to
    loopback and *default_port* so services don't listen on all interfaces or
    collide on a shared port unless configured to.

    An empty / whitespace-only value is treated as unset, not as a literal — a blank
    ``{prefix}_HOST`` export used to bind ``''`` (all interfaces) and a blank
    ``{prefix}_PORT`` raised ``int('')`` (#300)."""
    host = (os.environ.get(f"{prefix}_HOST") or "").strip() or "127.0.0.1"
    port_value = (os.environ.get(f"{prefix}_PORT") or "").strip()
    port = int(port_value) if port_value else default_port
    return host, port


def make_api_key_guard(prefix: str = "BLUE_DATA_API", open_paths=None):
    """FastAPI dependency enforcing mandatory-by-default API-key auth.

    Key read from ``{prefix}_KEY`` per request (so it can be set after import).
    When unset, data endpoints are refused (401) unless ``{prefix}_AUTH_DISABLED``
    is a truthy flag. Accepts ``X-API-Key`` or ``Authorization: Bearer``."""
    open_paths = frozenset(open_paths) if open_paths is not None else DEFAULT_OPEN_PATHS

    def require_api_key(request: Request) -> None:
        if request.url.path in open_paths:
            return
        expected = os.environ.get(f"{prefix}_KEY")
        if not expected:
            if env_flag(f"{prefix}_AUTH_DISABLED"):
                return
            raise HTTPException(
                status_code=401,
                detail=f"API key required. Set {prefix}_KEY, or {prefix}_AUTH_DISABLED=true to run without auth.",
            )
        provided = request.headers.get("x-api-key")
        if not provided:
            auth = request.headers.get("authorization", "")
            if auth[:7].lower() == "bearer ":
                provided = auth[7:].strip()
        # Constant-time so response timing does not leak how much of a guess matches. #243
        if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return require_api_key


def make_csrf_guard(open_paths=None):
    """FastAPI dependency rejecting state-changing requests sent with a
    browser-simple content type (form/multipart/text) that a cross-site HTML
    form could forge. JSON and bodyless requests pass."""
    open_paths = frozenset(open_paths) if open_paths is not None else DEFAULT_OPEN_PATHS

    def require_safe_content_type(request: Request) -> None:
        if request.method not in _STATE_CHANGING_METHODS or request.url.path in open_paths:
            return
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type in _CSRF_SIMPLE_CONTENT_TYPES:
            raise HTTPException(
                status_code=415,
                detail="State-changing requests must use application/json (CSRF protection).",
            )

    return require_safe_content_type


def security_dependencies(prefix: str = "BLUE_DATA_API", open_paths=None):
    """App-level FastAPI dependencies: [api-key guard, CSRF guard]."""
    from fastapi import Depends

    return [
        Depends(make_api_key_guard(prefix, open_paths)),
        Depends(make_csrf_guard(open_paths)),
    ]
