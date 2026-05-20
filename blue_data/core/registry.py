from blue_data.sources.memory_json_source import MemoryJSONSource


class Registry:
    """Generic registry abstraction backed by a JSONSource."""

    def __init__(self, name="REGISTRY", store=None):
        self.name = name
        self.store = store or MemoryJSONSource()

        if self.store.get("$") in (None, {}):
            self.store.set("$", {"contents": {}})

    def register_record(
        self,
        name,
        type,
        scope="/",
        description="",
        properties=None,
        created_by=None,
        icon=None,
    ):
        record = {
            "name": name,
            "type": type,
            "scope": scope,
            "description": description,
            "created_by": created_by,
            "properties": properties or {},
            "icon": icon,
            "contents": {},
        }

        key = self._record_key(name, type, scope)
        self.store.set(key, record)
        return record

    def get_record(self, name, type, scope="/"):
        return self.store.get(self._record_key(name, type, scope))

    
    def list_records(self):
        return [
            value
            for key, value in self.store.data.items()
            if (
                key != "$"
                and isinstance(value, dict)
                and "name" in value
                and "type" in value
                and "scope" in value
            )
        ]

    def deregister_record(self, name, type, scope="/"):
        self.store.delete(self._record_key(name, type, scope))

    def _record_key(self, name, type, scope="/"):
        return f"{scope.rstrip('/')}/{type}/{name}"

        