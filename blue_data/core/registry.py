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

    
    def list_records(self, record_type: str | None = None, scope: str | None = None):
        records = [
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

        if record_type is not None:
            records = [r for r in records if r.get("type") == record_type]

        if scope is not None:
            records = [r for r in records if r.get("scope") == scope]

        return records
    
    

    def deregister_record(self, name, type, scope="/"):
        self.store.delete(self._record_key(name, type, scope))

    def _record_key(self, name, type, scope="/"):
        return f"{scope.rstrip('/')}/{type}/{name}"

        