"""Regression tests for issue #88.

ConfigResolver.profile_values swallowed the 'no such profile' error and returned {},
so a misspelled --profile/BLUE_DATA_PROFILE or a selection pointing at a renamed or
removed profile ran silently against the environment and defaults. It now raises
ProfileError, except on a fresh install where the profiles file does not exist yet.
"""
import pytest

from blue_data.utils.config.profiles import DEFAULT_PROFILE, ProfileError, ProfileStore
from blue_data.utils.config.resolve import ConfigResolver
from blue_data.utils.config.spec import base_spec


def _resolver(store, profile):
    return ConfigResolver(base_spec(), store, profile=profile, environ={})


def test_missing_requested_profile_raises(tmp_path):
    store = ProfileStore(str(tmp_path))
    store.initialize()  # creates the profiles file with 'default'
    with pytest.raises(ProfileError, match="ghost"):
        _resolver(store, "ghost").profile_values()


def test_removed_selected_profile_raises(tmp_path):
    store = ProfileStore(str(tmp_path))
    store.initialize()
    store.add("staging", {"BLUE_DATA_LLM_MODEL": "x"})
    store.remove("staging")
    with pytest.raises(ProfileError, match="staging"):
        _resolver(store, "staging").profile_values()


def test_fresh_install_default_is_empty(tmp_path):
    # No profiles file yet: the default profile is allowed to be absent.
    store = ProfileStore(str(tmp_path))
    assert _resolver(store, DEFAULT_PROFILE).profile_values() == {}


def test_existing_profile_returns_its_values(tmp_path):
    store = ProfileStore(str(tmp_path))
    store.initialize()
    store.add("staging", {"BLUE_DATA_LLM_MODEL": "gpt-4o"})
    assert _resolver(store, "staging").profile_values() == {"BLUE_DATA_LLM_MODEL": "gpt-4o"}
