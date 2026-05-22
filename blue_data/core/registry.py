from __future__ import annotations

import json
from typing import Any

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

    
    
    def list_records(
        self,
        record_type: str | None = None,
        scope: str | None = None,
        recursive: bool = False,
    ):
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
            if recursive:
                records = [
                    r
                    for r in records
                    if r.get("scope") == scope
                    or r.get("scope", "").startswith(scope.rstrip("/") + "/")
                ]
            else:
                records = [r for r in records if r.get("scope") == scope]

        return records
        

    def deregister_record(self, name, type, scope="/"):
        self.store.delete(self._record_key(name, type, scope))

    def _record_key(self, name, type, scope="/"):
        return f"{scope.rstrip('/')}/{type}/{name}"

    def get_record_properties(self, name, type, scope="/"):
        record = self.get_record(name, type, scope)
        return (record or {}).get("properties", {})

    def get_record_property(self, name, type, scope, key):
        return self.get_record_properties(name, type, scope).get(key)

    def set_record_property(self, name, type, scope, key, value):
        record = self.get_record(name, type, scope)
        if not record:
            raise ValueError(f"Record not found: {scope}/{type}/{name}")

        record.setdefault("properties", {})
        record["properties"][key] = value

        self.store.set(self._record_key(name, type, scope), record)
        return record

    def get_record_description(self, name, type, scope="/"):
        record = self.get_record(name, type, scope)
        return (record or {}).get("description")

    def set_record_description(self, name, type, scope, description):
        record = self.get_record(name, type, scope)
        if not record:
            raise ValueError(f"Record not found: {scope}/{type}/{name}")

        record["description"] = description
        self.store.set(self._record_key(name, type, scope), record)
        return record
    
    def update_record(
        self,
        name,
        type,
        scope="/",
        description=None,
        properties=None,
        icon=None,
    ):
        original = self.get_record(name, type, scope)

        if not original:
            return self.register_record(
                name=name,
                type=type,
                scope=scope,
                description=description or "",
                properties=properties or {},
                icon=icon,
            )

        updated = dict(original)

        if description is not None:
            updated["description"] = description

        if icon is not None:
            updated["icon"] = icon

        if properties is not None:
            current_properties = updated.get("properties", {}) or {}
            current_properties.update(properties)
            updated["properties"] = current_properties

        self.store.set(self._record_key(name, type, scope), updated)
        return original, updated


    def deregister(self, record):
        if not record:
            return None

        return self.deregister_record(
            record["name"],
            record["type"],
            record["scope"],
        )


    def filter_record_contents(
        self,
        name,
        type,
        scope,
        filter_type=None,
        filter_name=None,
        single=False,
    ):
        parent_key = self._record_key(name, type, scope)
        parent_prefix = parent_key.rstrip("/") + "/"

        matches = []

        for key, value in self.store.data.items():
            if key == "$" or not isinstance(value, dict):
                continue

            if not key.startswith(parent_prefix):
                continue

            if filter_type is not None and value.get("type") != filter_type:
                continue

            if filter_name is not None and value.get("name") != filter_name:
                continue

            matches.append(value)

        if single:
            return matches[0] if matches else None

        return matches


    def dumps(self):
        return json.dumps(self.list_records(recursive=True), indent=2)


    def dump(self, output_file):
        with open(output_file, "w") as fp:
            json.dump(self.list_records(recursive=True), fp, indent=2)


    def loads(self, input_string):
        records = json.loads(input_string)
        self._load_records(records)


    def load(self, input_file):
        with open(input_file, "r") as fp:
            records = json.load(fp)
        self._load_records(records)


    def _load_records(self, records):
        for record in records:
            self.register_record(
                name=record["name"],
                type=record["type"],
                scope=record.get("scope", "/"),
                description=record.get("description", ""),
                properties=record.get("properties", {}),
                created_by=record.get("created_by"),
                icon=record.get("icon"),
            )

    def delete_record_property(self, name, type, scope, key):
        record = self.get_record(name, type, scope)
        if not record:
            return None

        record.setdefault("properties", {})
        deleted = record["properties"].pop(key, None)

        self.store.set(self._record_key(name, type, scope), record)
        return deleted
    
    def filter_records_by_properties(
        self,
        record_type: str | None = None,
        scope: str | None = None,
        properties: dict | None = None,
        recursive: bool = False,
        partial_match: bool = False,
    ):
        def match_props(record_props, filter_props):
            for key, expected in filter_props.items():
                actual = record_props.get(key)

                if isinstance(expected, dict):
                    if not isinstance(actual, dict):
                        return False
                    if not match_props(actual, expected):
                        return False
                else:
                    if partial_match:
                        if actual is None or str(expected) not in str(actual):
                            return False
                    else:
                        if actual != expected:
                            return False

            return True

        records = self.list_records(
            record_type=record_type,
            scope=scope,
            recursive=recursive,
        )

        if not properties:
            return records

        return [
            record
            for record in records
            if match_props(record.get("properties", {}) or {}, properties)
        ]

   