"""#95 — search must score every candidate, not just the first
page_limit*page_size records in store order."""
from blue_data.registry.data_registry import DataRegistry


def _build(target_first: bool) -> DataRegistry:
    reg = DataRegistry()

    def add(name, desc):
        reg.register_source_database_collection_entity(
            "src", "db", "public", name, description=desc
        )

    if target_first:
        add("invoices", "customer invoices and billing amounts")
    for i in range(120):
        add(f"table_{i:03d}", "filler table")
    if not target_first:
        add("invoices", "customer invoices and billing amounts")
    return reg


def test_record_registered_last_is_still_found():
    hits = _build(target_first=False).search_records("invoices", page_size=10)
    assert hits
    assert hits[0]["name"] == "invoices"
    assert any(h["name"] == "invoices" for h in hits)


def test_search_is_store_order_independent():
    for first in (True, False):
        hits = _build(first).search_records("invoices", page_size=10)
        assert hits and hits[0]["name"] == "invoices", f"failed with target_first={first}"
