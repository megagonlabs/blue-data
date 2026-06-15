import pytest
from blue_data.source.stream.memory_stream_source import MemoryStreamSource
from blue_data.source.stream.file_stream_source import FileStreamSource


# ===========================================================================
# MemoryStreamSource
# ===========================================================================

@pytest.fixture
def mem():
    return MemoryStreamSource(name="test_stream")


def test_publish_and_consume(mem):
    mem.publish("events", {"type": "click", "user": "alice"})
    msgs = mem.consume("events", count=1)
    assert len(msgs) == 1
    assert msgs[0]["type"] == "click"


def test_consume_advances_cursor(mem):
    mem.publish("events", {"n": 1})
    mem.publish("events", {"n": 2})
    mem.publish("events", {"n": 3})
    first = mem.consume("events", count=2)
    second = mem.consume("events", count=2)
    assert [m["n"] for m in first] == [1, 2]
    assert [m["n"] for m in second] == [3]


def test_consume_empty_stream(mem):
    assert mem.consume("empty") == []


def test_consume_count_larger_than_available(mem):
    mem.publish("s", {"x": 1})
    msgs = mem.consume("s", count=10)
    assert len(msgs) == 1


def test_consume_does_not_repeat(mem):
    mem.publish("s", {"v": 1})
    mem.consume("s", count=1)
    assert mem.consume("s", count=1) == []


def test_publish_multiple_streams(mem):
    mem.publish("a", {"src": "a"})
    mem.publish("b", {"src": "b"})
    assert mem.consume("a")[0]["src"] == "a"
    assert mem.consume("b")[0]["src"] == "b"


def test_create_stream(mem):
    result = mem.create_stream("orders")
    assert result["status"] == "success"
    assert mem.consume("orders") == []


def test_create_stream_idempotent(mem):
    mem.publish("s", {"v": 1})
    mem.create_stream("s")          # should not reset existing stream
    assert len(mem.consume("s", count=10)) == 1


def test_delete_stream(mem):
    mem.publish("temp", {"v": 1})
    mem.delete_stream("temp")
    assert mem.consume("temp") == []


def test_delete_resets_cursor(mem):
    mem.publish("s", {"v": 1})
    mem.consume("s")
    mem.delete_stream("s")
    mem.publish("s", {"v": 2})
    msgs = mem.consume("s")
    assert msgs[0]["v"] == 2


def test_acknowledge_no_error(mem):
    mem.acknowledge("s", "msg-001")   # no-op, should not raise


def test_properties_stored(mem):
    s = MemoryStreamSource(name="s2", properties={"region": "us-east"})
    assert s.properties["region"] == "us-east"


# ===========================================================================
# FileStreamSource
# ===========================================================================

@pytest.fixture
def file_src(tmp_path):
    return FileStreamSource(name="file_stream", directory=str(tmp_path))


def test_file_publish_and_consume(file_src):
    file_src.publish("logs", {"level": "INFO", "msg": "started"})
    msgs = file_src.consume("logs", count=1)
    assert len(msgs) == 1
    assert msgs[0]["level"] == "INFO"


def test_file_consume_advances_cursor(file_src):
    for i in range(5):
        file_src.publish("s", {"i": i})
    first = file_src.consume("s", count=3)
    second = file_src.consume("s", count=3)
    assert len(first) == 3
    assert len(second) == 2


def test_file_consume_empty_stream(file_src):
    assert file_src.consume("nonexistent") == []


def test_file_create_stream(file_src, tmp_path):
    result = file_src.create_stream("orders")
    assert result["status"] == "success"
    assert (tmp_path / "orders.jsonl").exists()


def test_file_delete_stream(file_src, tmp_path):
    file_src.publish("temp", {"v": 1})
    file_src.delete_stream("temp")
    assert not (tmp_path / "temp.jsonl").exists()
    assert file_src.consume("temp") == []


def test_file_delete_resets_cursor(file_src):
    file_src.publish("s", {"v": 1})
    file_src.consume("s")
    file_src.delete_stream("s")
    file_src.publish("s", {"v": 2})
    msgs = file_src.consume("s")
    assert msgs[0]["v"] == 2


def test_file_messages_persisted(file_src, tmp_path):
    file_src.publish("audit", {"action": "login"})
    path = tmp_path / "audit.jsonl"
    assert path.exists()
    assert path.read_text().strip() != ""


def test_file_acknowledge_no_error(file_src):
    file_src.acknowledge("s", "msg-001")
