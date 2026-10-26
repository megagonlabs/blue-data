"""Regression tests for issue #181.

Redis FT index names are global per database, so two tenants with different
scan_prefix values sharing a fixed name (registry_index, a collection name, 'web')
silently shared the first tenant's index. The source now namespaces the index name
by scan_prefix, and create_index refuses to reuse an existing index whose PREFIX or
DIM differs. Server-free: command builders and the create_index guard are exercised
with synthetic replies.
"""
import pytest

pytest.importorskip("redis")
from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource


def _src(scan_prefix):
    return RedisVectorSource(
        name="r", properties={"connection": {"host": "h", "port": 1, "scan_prefix": scan_prefix}}
    )


# ---------- index name is namespaced by scan_prefix ----------

def test_create_index_command_namespaces_index_name():
    cmd = _src("tenantA:")._build_create_index_command(
        {"index": "registry_index", "collection": "c", "dim": 8}
    )
    assert cmd[0] == "FT.CREATE"
    assert cmd[1] == "tenantA:registry_index"
    # the key PREFIX stays scan_prefix+collection
    i = cmd.index("PREFIX")
    assert cmd[i + 2] == "tenantA:c:"


def test_knn_command_namespaces_index_name():
    cmd = _src("tenantA:")._build_knn_command({"index": "registry_index", "vector": [0.1, 0.2]})
    assert cmd[0] == "FT.SEARCH"
    assert cmd[1] == "tenantA:registry_index"


def test_namespacing_is_idempotent():
    src = _src("tenantA:")
    assert src._namespaced_index("tenantA:registry_index") == "tenantA:registry_index"


def test_two_tenants_get_distinct_index_names():
    name = "documents_ns"
    cmd_a = _src("tenantA:")._build_create_index_command({"index": name, "collection": name, "dim": 8})
    cmd_b = _src("tenantB:")._build_create_index_command({"index": name, "collection": name, "dim": 8})
    assert cmd_a[1] == "tenantA:documents_ns"
    assert cmd_b[1] == "tenantB:documents_ns"
    assert cmd_a[1] != cmd_b[1]


# ---------- create_index refuses a mismatched existing index ----------

class _Conn:
    """Raises 'already exists' on FT.CREATE; returns a canned FT.INFO reply."""

    def __init__(self, info_reply=None, info_raises=False):
        self._info_reply = info_reply
        self._info_raises = info_raises

    def execute_command(self, *args):
        if args[0] == "FT.INFO":
            if self._info_raises:
                raise Exception("Unknown index name")
            return self._info_reply
        raise Exception("Index already exists")


def _ft_info_reply(prefix, dim):
    return [
        b"index_name", b"idx",
        b"index_definition", [b"key_type", b"JSON", b"prefixes", [prefix.encode()]],
        b"attributes", [[b"identifier", b"$.embedding", b"attribute", b"embedding",
                         b"type", b"VECTOR", b"dim", str(dim).encode()]],
    ]


def test_create_index_reuses_matching_existing_index():
    src = _src("tenantA:")
    src.connection = _Conn(info_reply=_ft_info_reply("tenantA:c:", 8))
    assert src.create_index("idx", "c", 8) == "OK"


def test_create_index_refuses_mismatched_prefix():
    src = _src("tenantB:")
    # existing index belongs to tenantA
    src.connection = _Conn(info_reply=_ft_info_reply("tenantA:c:", 8))
    with pytest.raises(Exception, match="different prefix or dimension"):
        src.create_index("idx", "c", 8)


def test_create_index_refuses_mismatched_dim():
    src = _src("tenantA:")
    src.connection = _Conn(info_reply=_ft_info_reply("tenantA:c:", 16))
    with pytest.raises(Exception, match="different prefix or dimension"):
        src.create_index("idx", "c", 8)


def test_create_index_ok_when_info_undeterminable():
    # FT.INFO failing must not break idempotency — reuse (OK), don't raise.
    src = _src("tenantA:")
    src.connection = _Conn(info_raises=True)
    assert src.create_index("idx", "c", 8) == "OK"
