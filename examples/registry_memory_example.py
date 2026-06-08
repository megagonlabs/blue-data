from registry.registry import Registry

registry = Registry()

registry.store.set(
    "sample",
    {
        "name": "users",
        "type": "collection",
    },
)

print(registry.store.get("sample"))