"""Regression guard for issue #273.

examples/backends/redis_demo.py manually created its vector index under
``"collection": "records"`` while the registry indexes under ``registry_records``;
since #215 stopped swallowing index-creation mismatches, that collided on the same
index name and aborted the demo. The fix drops the manual CREATE_INDEX and relies on
the registry owning index creation. This pins that invariant deterministically (with
an in-memory vector source, so no Redis): a DataRegistry wired with a vector source and
an ``index_name`` creates and uses its own index — search works with no manual
``VECTOR.CREATE_INDEX``.
"""
import numpy as np

from blue_data.registry.data_registry import DataRegistry
from blue_data.source.json.memory_json_source import MemoryJSONSource
from blue_data.source.vector.memory_vector_source import MemoryVectorSource

DIM = 32


def _embed(text: str) -> list:
    rng = np.random.RandomState(abs(hash(text)) % (2**31))
    return rng.randn(DIM).tolist()


def test_registry_creates_and_uses_its_own_index_without_manual_create():
    reg = DataRegistry(
        store=MemoryJSONSource(),
        vector_source=MemoryVectorSource(),
        embedding_fn=_embed,
        vector_dim=DIM,
        index_name="demo-idx",
        rebuild=True,
        hybrid_config={"vector_threshold": 0.0, "combined_threshold": 0.0},
    )
    # No VECTOR.CREATE_INDEX here — the registry owns index creation when it indexes.
    reg.register_record("orders", "entity", "/source/shop", description="customer orders")
    reg.register_record("shipments", "entity", "/source/shop", description="outbound shipments")

    results = reg.search_records("orders")  # must not raise "No such index"; ranked records
    assert isinstance(results, list)
    assert any(r.get("name") == "orders" for r in results)
