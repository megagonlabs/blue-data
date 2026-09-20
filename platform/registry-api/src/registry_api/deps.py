from blue_data.registry.data_registry import DataRegistry
from registry_api.config import get_registry as _get_registry


def get_registry() -> DataRegistry:
    """FastAPI dependency — override in tests via app.dependency_overrides."""
    return _get_registry()
