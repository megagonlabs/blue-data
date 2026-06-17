"""Unit tests for StreamSource.execute_query on MemoryStreamSource."""
import pytest

from blue_data.source.stream.memory_stream_source import MemoryStreamSource


@pytest.fixture
def src():
    return MemoryStreamSource("mem")


class TestCreate:
    def test_create_stream(self, src):
        result = src.execute_query({"op": "STREAM.CREATE", "stream": "events"})
        assert result == {"status": "success"}

    def test_create_returns_none_not_raised(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "s"})


class TestPublishAndConsume:
    def test_publish_returns_none(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "logs"})
        result = src.execute_query(
            {"op": "STREAM.PUBLISH", "stream": "logs", "message": {"level": "info", "text": "hi"}}
        )
        assert result is None

    def test_consume_returns_messages(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "q"})
        src.execute_query({"op": "STREAM.PUBLISH", "stream": "q", "message": {"n": 1}})
        src.execute_query({"op": "STREAM.PUBLISH", "stream": "q", "message": {"n": 2}})
        msgs = src.execute_query({"op": "STREAM.CONSUME", "stream": "q", "count": 2})
        assert len(msgs) == 2
        assert msgs[0]["n"] == 1

    def test_consume_default_count_one(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "s"})
        src.execute_query({"op": "STREAM.PUBLISH", "stream": "s", "message": {"x": 1}})
        src.execute_query({"op": "STREAM.PUBLISH", "stream": "s", "message": {"x": 2}})
        msgs = src.execute_query({"op": "STREAM.CONSUME", "stream": "s"})
        assert len(msgs) == 1


class TestAcknowledge:
    def test_acknowledge_no_error(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "s"})
        result = src.execute_query(
            {"op": "STREAM.ACKNOWLEDGE", "stream": "s", "message_id": "msg-1"}
        )
        assert result is None


class TestDelete:
    def test_delete_stream(self, src):
        src.execute_query({"op": "STREAM.CREATE", "stream": "tmp"})
        result = src.execute_query({"op": "STREAM.DELETE", "stream": "tmp"})
        assert result is None
        assert src.execute_query({"op": "STREAM.CONSUME", "stream": "tmp"}) == []


class TestErrors:
    def test_non_dict_query_raises(self, src):
        with pytest.raises(ValueError, match="expects query as a dict"):
            src.execute_query("PUBLISH events hello")

    def test_unknown_op_raises(self, src):
        with pytest.raises(ValueError, match="Unsupported"):
            src.execute_query({"op": "STREAM.PEEK", "stream": "s"})
