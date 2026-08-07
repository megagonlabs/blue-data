"""Unit tests for the DataSource lifecycle and property-merge logic."""
import logging

import pytest

from blue_data.source.source import DataSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ConnRecorder(DataSource):
    """Captures _connect / _disconnect call signatures."""

    def __init__(self, name="recorder", properties=None):
        self.connected_with = None
        self.disconnected = False
        super().__init__(name, properties=properties)

    def _connect(self, **connection):
        self.connected_with = dict(connection)
        return "live_connection"

    def _disconnect(self):
        self.disconnected = True


class _CustomDefaults(DataSource):
    """Sets extra default properties in _initialize_connection_properties."""

    def _initialize_connection_properties(self):
        self.properties["connection"] = {
            "protocol": "custom",
            "host": "localhost",
            "port": 9999,
        }


# ===========================================================================
# Default state after __init__
# ===========================================================================

class TestDefaults:
    def test_name_stored(self):
        src = DataSource("my_source")
        assert src.name == "my_source"

    def test_default_connection_property(self):
        src = DataSource("s")
        assert src.properties["connection"]["protocol"] == "default"

    def test_logger_attached(self):
        src = DataSource("s")
        assert isinstance(src.logger, logging.Logger)
        assert src.logger.name == "DataSource"

    def test_logger_named_after_subclass(self):
        src = _ConnRecorder()
        assert src.logger.name == "_ConnRecorder"

    def test_connection_set_to_connect_return_value(self):
        src = _ConnRecorder()
        assert src.connection == "live_connection"

    def test_base_connect_returns_none(self):
        src = DataSource("s")
        assert src.connection is None

    def test_none_properties_treated_as_empty(self):
        src = DataSource("s", properties=None)
        assert isinstance(src.properties, dict)


# ===========================================================================
# _update_properties / deep merge
# ===========================================================================

class TestUpdateProperties:
    def test_top_level_scalar_merged(self):
        src = DataSource("s", properties={"timeout": 30})
        assert src.properties["timeout"] == 30

    def test_connection_dict_deep_merged(self):
        src = _CustomDefaults("s", properties={"connection": {"host": "prod.example.com"}})
        conn = src.properties["connection"]
        assert conn["host"] == "prod.example.com"
        assert conn["port"] == 9999
        assert conn["protocol"] == "custom"

    def test_user_value_overrides_default(self):
        src = _CustomDefaults("s", properties={"connection": {"port": 1234}})
        assert src.properties["connection"]["port"] == 1234

    def test_non_dict_value_replaces_dict(self):
        src = DataSource("s")
        src.properties["metadata"] = {"nested": "val"}
        src._update_properties(properties={"metadata": "flat_string"})
        assert src.properties["metadata"] == "flat_string"

    def test_empty_properties_leaves_defaults(self):
        src = _CustomDefaults("s", properties={})
        assert src.properties["connection"]["host"] == "localhost"

    def test_extra_key_added(self):
        src = DataSource("s", properties={"region": "us-east-1"})
        assert src.properties["region"] == "us-east-1"


# ===========================================================================
# _deep_merge standalone
# ===========================================================================

class TestDeepMerge:
    def _merge(self, base, update):
        return DataSource("s")._deep_merge(base, update)

    def test_flat_update(self):
        result = self._merge({"a": 1, "b": 2}, {"b": 99, "c": 3})
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_dict_merged_recursively(self):
        base = {"conn": {"host": "localhost", "port": 5432}}
        update = {"conn": {"host": "remote"}}
        result = self._merge(base, update)
        assert result["conn"]["host"] == "remote"
        assert result["conn"]["port"] == 5432

    def test_nested_non_dict_replaces_dict(self):
        base = {"conn": {"host": "localhost"}}
        update = {"conn": "tcp://remote"}
        result = self._merge(base, update)
        assert result["conn"] == "tcp://remote"

    def test_base_not_mutated(self):
        base = {"a": {"x": 1}}
        _ = self._merge(base, {"a": {"x": 2}})
        assert base["a"]["x"] == 1

    def test_deeply_nested(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        update = {"a": {"b": {"c": 99}}}
        result = self._merge(base, update)
        assert result["a"]["b"]["c"] == 99
        assert result["a"]["b"]["d"] == 2

    def test_empty_update_returns_copy(self):
        base = {"x": 1}
        result = self._merge(base, {})
        assert result == {"x": 1}

    def test_empty_base_returns_update(self):
        result = self._merge({}, {"x": 1})
        assert result == {"x": 1}


# ===========================================================================
# _connect called with correct kwargs
# ===========================================================================

class TestConnectKwargs:
    def test_connect_receives_connection_dict_as_kwargs(self):
        src = _ConnRecorder(
            properties={"connection": {"protocol": "custom", "host": "db.local", "port": 5432}}
        )
        assert src.connected_with["protocol"] == "custom"
        assert src.connected_with["host"] == "db.local"
        assert src.connected_with["port"] == 5432

    def test_connect_receives_default_protocol(self):
        src = _ConnRecorder()
        assert src.connected_with["protocol"] == "default"


# ===========================================================================
# _stop / _disconnect
# ===========================================================================

class TestStop:
    def test_stop_calls_disconnect(self):
        src = _ConnRecorder()
        assert not src.disconnected
        src._stop()
        assert src.disconnected

    def test_base_disconnect_returns_none(self):
        src = DataSource("s")
        assert src._disconnect() is None

    def test_stop_logs_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="_ConnRecorder"):
            src = _ConnRecorder()
            src._stop()
        assert any("Stopped" in r.message for r in caplog.records)


# ===========================================================================
# _initialize_connection_properties override isolation
# ===========================================================================

class TestConnectionPropertyOverride:
    def test_subclass_defaults_visible_after_init(self):
        src = _CustomDefaults("s")
        assert src.properties["connection"]["protocol"] == "custom"

    def test_subclass_defaults_do_not_bleed_into_base(self):
        src = DataSource("s")
        assert src.properties["connection"]["protocol"] == "default"

    def test_user_props_merged_over_subclass_defaults(self):
        src = _CustomDefaults("s", properties={"connection": {"port": 42}})
        assert src.properties["connection"]["port"] == 42
        assert src.properties["connection"]["host"] == "localhost"


# ===========================================================================
# DataSource.instantiate
# ===========================================================================

class TestInstantiate:
    def test_instantiate_base_class(self):
        src = DataSource.instantiate(
            "blue_data.source.source.DataSource",
            "from_path",
        )
        assert src.name == "from_path"
        assert isinstance(src, DataSource)

    def test_instantiate_subclass(self):
        src = DataSource.instantiate(
            "blue_data.source.vector.memory_vector_source.MemoryVectorSource",
            "vec",
        )
        from blue_data.source.vector.memory_vector_source import MemoryVectorSource
        assert isinstance(src, MemoryVectorSource)

    def test_instantiate_bad_path_raises(self):
        with pytest.raises((ImportError, AttributeError, ModuleNotFoundError)):
            DataSource.instantiate("blue_data.source.source.NoSuchClass", "x")
