from blue_data.core.utils.utils import deep_merge


def test_flat_merge():
    result = deep_merge({"a": 1}, {"b": 2})
    assert result == {"a": 1, "b": 2}


def test_override():
    result = deep_merge({"a": 1}, {"a": 99})
    assert result["a"] == 99


def test_nested_merge():
    base = {"a": {"x": 1, "y": 2}}
    update = {"a": {"y": 99, "z": 3}}
    result = deep_merge(base, update)
    assert result == {"a": {"x": 1, "y": 99, "z": 3}}


def test_does_not_mutate_base():
    base = {"a": 1}
    deep_merge(base, {"b": 2})
    assert "b" not in base
