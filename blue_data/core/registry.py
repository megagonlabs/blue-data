from blue_data.core.stores.memory_json_source import MemoryJSONSource


class Registry:
    """Generic registry abstraction."""

    def __init__(self, name="REGISTRY", store=None):
        self.name = name
        self.store = store or MemoryJSONSource()