"""
Registry in-memory example.

Covers the full public API surface using only in-memory backends:
  - Registry CRUD (register, get, update, list, deregister)
  - Properties and descriptions at every hierarchy level
  - filter_records_by_properties (exact and partial)
  - register_record_json with nested contents (old-format import)
  - dumps / loads round-trip serialization
  - rebuild flag (three-state: True / False / None)
  - Hybrid search (BM25 + vector) with MemoryVectorSource
  - Keyword-only search fallback (no vector source)

No database or Redis required.
"""
import hashlib
import json
import math

from blue_data.registry.data_registry import DataRegistry
from blue_data.registry.registry import Registry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

DIVIDER = "-" * 60


# ---------------------------------------------------------------------------
# Embedding function (deterministic hash-based, no model needed)
# ---------------------------------------------------------------------------

DIM = 64


def simple_embedding(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [math.sin(seed * (i + 1) * 0.1) for i in range(DIM)]


# ---------------------------------------------------------------------------
# 1. Basic Registry CRUD
# ---------------------------------------------------------------------------

print(DIVIDER)
print("1. Basic Registry CRUD")
print(DIVIDER)

reg = Registry(store=MemoryJSONSource())

reg.register_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Stores user accounts and profile data",
    properties={"owner": "platform-team"},
)
reg.register_record(
    name="orders",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Customer purchase orders",
    properties={"owner": "commerce-team"},
)
reg.register_record(
    name="products",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="Product catalog with pricing",
    properties={"owner": "catalog-team"},
)

record = reg.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
print("get_record('users'):", record["name"], "—", record["description"])

all_records = reg.list_records()
print(f"list_records() → {len(all_records)} records")

reg.update_record(
    name="users",
    type="entity",
    scope="/source/mydb/database/prod/collection/public",
    description="User accounts, profile data, and preferences",
    properties={"pii": True},
)
updated = reg.get_record("users", "entity", "/source/mydb/database/prod/collection/public")
print("After update — users.description:", updated["description"])
print("After update — users.properties:", updated["properties"])

reg.set_record_property("orders", "entity", "/source/mydb/database/prod/collection/public", "status", "active")
print("get_record_property('orders', 'status'):",
      reg.get_record_property("orders", "entity", "/source/mydb/database/prod/collection/public", "status"))

reg.set_record_description("products", "entity", "/source/mydb/database/prod/collection/public", "Product catalog — managed by catalog-team")
print("get_record_description('products'):",
      reg.get_record_description("products", "entity", "/source/mydb/database/prod/collection/public"))

reg.delete_record_property("orders", "entity", "/source/mydb/database/prod/collection/public", "status")
print("After delete_record_property('status'):",
      reg.get_record_property("orders", "entity", "/source/mydb/database/prod/collection/public", "status"))

reg.deregister_record("products", "entity", "/source/mydb/database/prod/collection/public")
print("After deregister — list_records count:", len(reg.list_records()))


# ---------------------------------------------------------------------------
# 2. list_records with scope and recursive
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("2. list_records — scope and recursive filtering")
print(DIVIDER)

reg2 = Registry(store=MemoryJSONSource())
reg2.register_record("mydb", "database", "/source/s1")
reg2.register_record("public", "collection", "/source/s1/database/mydb")
reg2.register_record("users", "entity", "/source/s1/database/mydb/collection/public")
reg2.register_record("otherdb", "database", "/source/s2")

scoped = reg2.list_records(scope="/source/s1", recursive=True)
print("list_records(scope='/source/s1', recursive=True):", [r["name"] for r in scoped])

non_recursive = reg2.list_records(scope="/source/s1")
print("list_records(scope='/source/s1', recursive=False):", [r["name"] for r in non_recursive])


# ---------------------------------------------------------------------------
# 3. filter_records_by_properties
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("3. filter_records_by_properties — exact and partial")
print(DIVIDER)

reg3 = Registry(store=MemoryJSONSource())
reg3.register_record("transactions", "entity", "/source/db", properties={"domain": "finance", "owner": "finance-team"})
reg3.register_record("shipments", "entity", "/source/db", properties={"domain": "logistics", "owner": "ops-team"})
reg3.register_record("invoices", "entity", "/source/db", properties={"domain": "finance", "owner": "finance-team"})

exact = reg3.filter_records_by_properties(properties={"domain": "finance"})
print("Exact match domain=finance:", [r["name"] for r in exact])

partial = reg3.filter_records_by_properties(properties={"owner": "finance"}, partial_match=True)
print("Partial match owner contains 'finance':", [r["name"] for r in partial])

nested = reg3.filter_records_by_properties(properties={"domain": "logistics"}, record_type="entity")
print("Exact match logistics + type filter:", [r["name"] for r in nested])


# ---------------------------------------------------------------------------
# 4. register_record_json with nested contents (old-format import)
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("4. register_record_json — nested contents import")
print(DIVIDER)

nested_record = {
    "name": "sales",
    "type": "database",
    "scope": "/source/crm",
    "description": "Sales database",
    "properties": {},
    "contents": {
        "collection": {
            "public": {
                "name": "public",
                "type": "collection",
                "scope": "/source/crm/database/sales",
                "description": "Default schema",
                "properties": {},
                "contents": {
                    "entity": {
                        "deals": {
                            "name": "deals",
                            "type": "entity",
                            "scope": "/source/crm/database/sales/collection/public",
                            "description": "Sales pipeline deals",
                            "properties": {"pk": "deal_id"},
                            "contents": {
                                "attribute": {
                                    "deal_id": {
                                        "name": "deal_id",
                                        "type": "attribute",
                                        "scope": "/source/crm/database/sales/collection/public/entity/deals",
                                        "description": "Primary key",
                                        "properties": {"info": {"type": "UUID"}},
                                        "contents": {},
                                    },
                                    "amount": {
                                        "name": "amount",
                                        "type": "attribute",
                                        "scope": "/source/crm/database/sales/collection/public/entity/deals",
                                        "description": "Deal value in USD",
                                        "properties": {"info": {"type": "NUMERIC"}},
                                        "contents": {},
                                    },
                                }
                            },
                        }
                    }
                },
            }
        }
    },
}

reg4 = Registry(store=MemoryJSONSource())
reg4.register_record_json(nested_record)

print("database record:", reg4.get_record("sales", "database", "/source/crm")["description"])
print("collection record:", reg4.get_record("public", "collection", "/source/crm/database/sales")["description"])
print("entity record:", reg4.get_record("deals", "entity", "/source/crm/database/sales/collection/public")["description"])
attr = reg4.get_record("deal_id", "attribute", "/source/crm/database/sales/collection/public/entity/deals")
print("attribute record:", attr["name"], "—", attr["description"])
print("All records imported:", [r["name"] for r in reg4.list_records()])


# ---------------------------------------------------------------------------
# 5. dumps / loads round-trip serialization
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("5. dumps / loads — round-trip serialization")
print(DIVIDER)

source_reg = Registry(store=MemoryJSONSource())
source_reg.register_record("db1", "database", "/source/mydb", description="Primary DB")
source_reg.register_record("public", "collection", "/source/mydb/database/db1", description="Public schema")
source_reg.register_record("customers", "entity", "/source/mydb/database/db1/collection/public", description="Customer records")
source_reg.set_record_property("customers", "entity", "/source/mydb/database/db1/collection/public", "pk", "customer_id")

serialized = source_reg.dumps()
print("Serialized to JSON, length:", len(serialized), "chars")

restored_reg = Registry(store=MemoryJSONSource())
restored_reg.loads(serialized)

r = restored_reg.get_record("customers", "entity", "/source/mydb/database/db1/collection/public")
print("Restored 'customers' description:", r["description"])
print("Restored 'customers' pk property:", r["properties"]["pk"])
print("Restored record count:", len(restored_reg.list_records()))


# ---------------------------------------------------------------------------
# 6. set_record_data / get_record_data / delete_record_data
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("6. set_record_data / get_record_data / delete_record_data")
print(DIVIDER)

reg5 = Registry(store=MemoryJSONSource())
reg5.register_record("events", "entity", "/source/mydb")
reg5.set_record_data("events", "entity", "/source/mydb", key="lineage", value={"source": "kafka", "pipeline": "v2"})
print("get_record_data('lineage'):", reg5.get_record_data("events", "entity", "/source/mydb", key="lineage"))
reg5.delete_record_data("events", "entity", "/source/mydb", key="lineage")
print("After delete_record_data:", reg5.get_record_data("events", "entity", "/source/mydb", key="lineage"))


# ---------------------------------------------------------------------------
# 7. rebuild flag — three-state behavior
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("7. rebuild flag — True / False / None")
print(DIVIDER)

indexed = []

class TrackingVectorSource(MemoryVectorSource):
    def execute_query(self, query):
        if isinstance(query, dict) and query.get("op") == "VECTOR.UPSERT":
            indexed.append(query.get("doc", {}).get("name"))
        return super().execute_query(query)

dreg = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=TrackingVectorSource(),
    embedding_fn=simple_embedding,
    vector_dim=DIM,
    rebuild=True,
)

# rebuild=True on instance → auto-index
dreg.register_record("alpha", "entity", "/source/db", rebuild=None)
print("rebuild=None (instance default True) — indexed:", "alpha" in indexed)

prev_count = len(indexed)
# rebuild=False → suppresses index even though instance default is True
dreg.register_record("beta", "entity", "/source/db", rebuild=False)
print("rebuild=False — beta indexed:", "beta" in indexed)

# rebuild=True → forces index even if instance default were False
dreg2 = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=TrackingVectorSource(),
    embedding_fn=simple_embedding,
    vector_dim=DIM,
    rebuild=False,
)
dreg2.register_record("gamma", "entity", "/source/db", rebuild=True)
print("rebuild=True (instance default False) — gamma indexed:", any("gamma" in str(x) for x in indexed))


# ---------------------------------------------------------------------------
# 8. Hybrid search (BM25 + vector)
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("8. Hybrid search — BM25 + vector")
print(DIVIDER)

search_reg = DataRegistry(
    store=MemoryJSONSource(),
    vector_source=MemoryVectorSource(),
    embedding_fn=simple_embedding,
    vector_dim=DIM,
    rebuild=True,
    hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
)

search_reg.register_record(
    name="customer_orders",
    type="entity",
    scope="/source/shop/database/prod/collection/public",
    description="All customer purchase orders and their status",
)
search_reg.register_record(
    name="products",
    type="entity",
    scope="/source/shop/database/prod/collection/public",
    description="Product catalog with pricing and inventory",
)
search_reg.register_record(
    name="users",
    type="entity",
    scope="/source/shop/database/prod/collection/public",
    description="Registered user accounts",
)

results = search_reg.search_records("customer purchase orders")
print("search_records('customer purchase orders'):")
for r in results[:3]:
    print(f"  [{r.get('_score', 0):.3f}] {r['name']} — {r['description']}")

type_filtered = search_reg.search_records("products", type="entity")
print("search_records('products', type='entity') types:", {r["type"] for r in type_filtered})

scope_filtered = search_reg.search_records("users", scope="/source/shop")
print("search_records('users', scope='/source/shop'):", [r["name"] for r in scope_filtered])


# ---------------------------------------------------------------------------
# 9. Keyword-only search (no vector source)
# ---------------------------------------------------------------------------

print()
print(DIVIDER)
print("9. Keyword-only search — no vector source")
print(DIVIDER)

kw_reg = DataRegistry(store=MemoryJSONSource())
kw_reg.register_record("payments", "entity", "/source/fin", description="Payment records")
kw_reg.register_record("refunds", "entity", "/source/fin", description="Refund transactions")

results = kw_reg.search_engine.keyword_search("payment")
print("keyword_search('payment'):")
for r in results:
    print(f"  [score={r['score']}] {r['record']['name']} — {r['record']['description']}")
