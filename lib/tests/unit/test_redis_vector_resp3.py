"""#141 — RedisVectorSource must parse RESP3 FT.SEARCH replies and return the full
document by default. Pure command/parse methods — no Redis server required."""
import pytest

pytest.importorskip("redis")
from blue_data.source.vector.redis.redis_vector_source import RedisVectorSource


@pytest.fixture
def vec():
    return RedisVectorSource(
        name="v",
        properties={"connection": {"host": "localhost", "port": 6399, "scan_prefix": "t:"}},
    )


def _return_clause(cmd):
    i = cmd.index("RETURN")
    n = int(cmd[i + 1])
    return cmd[i + 2: i + 2 + n]


def test_knn_returns_full_document_by_default(vec):
    cmd = vec._build_knn_command({"index": "idx", "vector": [0.1, 0.2, 0.3], "k": 3})
    fields = _return_clause(cmd)
    assert "$" in fields      # full JSON document, not only the score
    assert "score" in fields


def test_knn_respects_explicit_return_fields(vec):
    cmd = vec._build_knn_command(
        {"index": "idx", "vector": [0.1, 0.2], "return_fields": ["text", "url"]}
    )
    fields = _return_clause(cmd)
    assert {"text", "url", "score"} <= set(fields)
    assert "$" not in fields


def test_parse_resp2_list_reply(vec):
    resp = [1, b"t:web:1", [b"$", b'{"text":"hello","url":"http://x"}', b"score", b"0.12"]]
    rows = vec._parse_search_results(resp)
    assert len(rows) == 1
    assert rows[0]["id"] == "t:web:1"
    assert rows[0]["document"] == {"text": "hello", "url": "http://x"}
    assert rows[0]["score"] == 0.12 and isinstance(rows[0]["score"], float)  # #180


def test_parse_resp3_mapping_reply(vec):
    resp = {
        "total_results": 1,
        "results": [
            {"id": "t:web:1",
             "extra_attributes": {"$": '{"text":"hello","url":"http://x"}', "score": "0.12"}},
        ],
    }
    rows = vec._parse_search_results(resp)
    assert len(rows) == 1
    assert rows[0]["id"] == "t:web:1"
    assert rows[0]["document"] == {"text": "hello", "url": "http://x"}
    assert rows[0]["score"] == 0.12 and isinstance(rows[0]["score"], float)  # #180


def test_parse_resp3_bytes_keys(vec):
    resp = {
        b"total_results": 1,
        b"results": [
            {b"id": b"t:web:2",
             b"extra_attributes": {b"$": b'{"text":"hi"}', b"score": b"0.5"}},
        ],
    }
    rows = vec._parse_search_results(resp)
    assert rows and rows[0]["id"] == "t:web:2"
    assert rows[0]["document"] == {"text": "hi"}
    assert rows[0]["score"] == 0.5 and isinstance(rows[0]["score"], float)  # #180
