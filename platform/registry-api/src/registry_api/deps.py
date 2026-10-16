from blue_data.registry.data_registry import DataRegistry
from blue_data.server import (
    DEFAULT_OPEN_PATHS,
    env_flag,
    make_api_key_guard,
    make_csrf_guard,
)
from registry_api.config import get_registry as _get_registry

_PREFIX = "BLUE_DATA_API"
_OPEN_PATHS = set(DEFAULT_OPEN_PATHS)


def get_registry() -> DataRegistry:
    """FastAPI dependency — override in tests via app.dependency_overrides."""
    return _get_registry()


def writes_enabled() -> bool:
    return env_flag(f"{_PREFIX}_ALLOW_WRITES")


def auth_disabled() -> bool:
    return env_flag(f"{_PREFIX}_AUTH_DISABLED")


# App-wide security dependencies, bound to the registry API's env prefix.
require_api_key = make_api_key_guard(_PREFIX, _OPEN_PATHS)
require_safe_content_type = make_csrf_guard(_OPEN_PATHS)
