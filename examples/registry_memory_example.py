"""
Registry in-memory example.

Shows the core public API: register, get, update, list, search.
No database or Redis required — uses MemoryJSONSource and MemoryVectorSource.
"""
import hashlib
import json
import math

from registry.data_registry import DataRegistry
from source.json.memory_json_source import MemoryJSONSource
from source.vector.memory_vector_source import MemoryVectorSource

# --- embedding function (hash-based, no model needed) ---
DIM = 64

def simple_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# --- build a registry with in-memory storage and vector search ---
registry = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=simple_embedding,
    vector_dim=DIM,
    rebuild=True,
)

# --- register some records ---
registry.register_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Stores user accounts and profile data",
)
registry.register_record(
    name="orders",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Customer purchase orders linked to users",
)
registry.register_record(
    name="products",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Product catalog with pricing and inventory",
)

# --- get a single record ---
record = registry.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
print("get_record('users'):")
print(json.dumps({k: v for k, v in record.items() if k != "contents"}, indent=2))
print()

# --- list all records ---
all_records = registry.list_records()
print(f"list_records() → {len(all_records)} records:")
for r in all_records:
    print(f"  [{r['type']}] {r['name']} — {r['description']}")
print()

# --- update a record (adds/merges properties) ---
registry.update_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    properties={"metadata": {"owner": "platform-team", "pii": True}},
)
updated = registry.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
print("After update_record — users.properties:")
print(json.dumps(updated["properties"], indent=2))
print()

# --- set a property directly ---
registry.set_record_property(
    name="orders",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    key="status",
    value="active",
)
print("get_record_property('orders', 'status'):",
      registry.get_record_property("orders", "entity",
                                   "/source/mydb/database/prod/collection/public", "status"))
print()

# --- search ---
print("search_records('user accounts'):")
results = registry.search_records(
    "user accounts",
    vector_threshold=0.0,
    combined_threshold=0.0,
)
for r in results:
    print(f"  [{r.get('_score', 0):.3f}] {r['name']} — {r['description']}")
