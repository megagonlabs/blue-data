import json
import os
import stat

import pytest

from blue_data.utils.config import (
    ConfigError,
    ConfigResolver,
    ProfileError,
    ProfileStore,
    base_spec,
    build_resolver,
    decode,
    display,
    encode,
    load_spec,
    spec_from_dict,
)

SPEC = {
    "BLUE_DATA_LLM_MODEL": {"default": "gpt-4o", "prompt": "Model", "required": True, "cast": "str"},
    "APP_LLM_MODEL": {"prompt": "App model", "cast": "str", "inherits": "BLUE_DATA_LLM_MODEL"},
    "APP_EXTRACTION_LLM_MODEL": {
        "prompt": "Extraction model", "cast": "str",
        "inherits": ["APP_LLM_MODEL", "BLUE_DATA_LLM_MODEL"],
    },
    "APP_DATA_DIR": {"default": "~/.app", "prompt": "Data dir", "required": True, "cast": "directory"},
    "APP_WORKERS": {"default": 1, "prompt": "Workers", "cast": "int"},
    "APP_DEBUG": {"default": False, "prompt": "Debug", "cast": "bool"},
    "OPENAI_API_KEY": {"prompt": "Key", "required": True, "cast": "secret"},
}


@pytest.fixture
def spec():
    return spec_from_dict(SPEC)


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path / "home")


def resolver(spec, store, env=None, profile=None):
    return ConfigResolver(spec, store, profile=profile, environ=dict(env or {}))


# ------------------------------------------------------------------ #
# spec + casts                                                        #
# ------------------------------------------------------------------ #

def test_base_spec_declares_the_family_wide_parameters():
    s = base_spec()
    assert "OPENAI_API_KEY" in s
    assert "BLUE_DATA_LLM_MODEL" in s
    assert "BLUE_DATA_CLI_FORMAT" in s
    assert "BLUE_DATA_CLI_LOG_LIMIT" in s
    assert s["OPENAI_API_KEY"].is_secret


def test_required_selects_what_an_interactive_walkthrough_asks(spec):
    assert [p.name for p in spec.required()] == [
        "BLUE_DATA_LLM_MODEL", "APP_DATA_DIR", "OPENAI_API_KEY",
    ]


@pytest.mark.parametrize("cast,raw,expected", [
    ("int", "3", 3),
    ("float", "1.5", 1.5),
    ("bool", "yes", True),
    ("bool", "off", False),
    ("str", " x ", "x"),
])
def test_casts_convert(cast, raw, expected):
    s = spec_from_dict({"P": {"cast": cast}})
    assert s["P"].cast_value(raw) == expected


def test_directory_cast_expands_user(spec):
    assert spec["APP_DATA_DIR"].cast_value("~/x") == os.path.expanduser("~/x")


def test_a_bad_value_names_the_parameter(spec):
    with pytest.raises(ConfigError, match="APP_WORKERS"):
        spec["APP_WORKERS"].cast_value("not-a-number")


def test_an_unknown_cast_is_rejected_at_load_time():
    with pytest.raises(ConfigError, match="nope"):
        spec_from_dict({"P": {"cast": "nope"}})


def test_an_unknown_parameter_error_lists_what_is_known(spec):
    with pytest.raises(ConfigError, match="APP_WORKERS"):
        spec["NO_SUCH_PARAM"]


def test_specs_compose_with_the_later_one_winning(spec):
    override = spec_from_dict({"BLUE_DATA_LLM_MODEL": {"default": "gpt-5", "cast": "str"}})
    merged = spec.merged_with(override)
    assert merged["BLUE_DATA_LLM_MODEL"].default == "gpt-5"
    assert "APP_DATA_DIR" in merged


def test_load_spec_reads_a_json_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"P": {"default": "v", "cast": "str"}}))
    assert load_spec(p)["P"].default == "v"


# ------------------------------------------------------------------ #
# profiles file                                                       #
# ------------------------------------------------------------------ #

def test_add_list_and_remove_profiles(store):
    store.add("default")
    store.add("staging", {"APP_WORKERS": "4"})
    assert store.list_profiles() == ["default", "staging"]
    assert store.values("staging") == {"APP_WORKERS": "4"}
    store.remove("staging")
    assert store.list_profiles() == ["default"]


def test_adding_a_duplicate_profile_is_refused(store):
    store.add("default")
    with pytest.raises(ProfileError, match="already exists"):
        store.add("default")


def test_removing_an_unknown_profile_is_refused(store):
    with pytest.raises(ProfileError, match="no such profile"):
        store.remove("ghost")


def test_keys_keep_their_case(store):
    """configparser lowercases option names by default; these keys are
    environment-variable names, so that would corrupt every one of them."""
    store.add("default", {"BLUE_DATA_LLM_MODEL": "gpt-4o"})
    assert list(store.values("default")) == ["BLUE_DATA_LLM_MODEL"]


def test_a_percent_in_a_value_survives(store):
    """configparser's default interpolation would read '%' as a directive."""
    store.add("default", {"OPENAI_API_KEY": "abc%def%ghi"})
    assert store.values("default")["OPENAI_API_KEY"] == "abc%def%ghi"


def test_the_profiles_file_is_not_world_readable(store):
    store.add("default", {"OPENAI_API_KEY": "enc:x"})
    mode = stat.S_IMODE(store.profiles_path.stat().st_mode)
    assert mode & (stat.S_IRGRP | stat.S_IROTH) == 0


def test_selection_defaults_to_default_and_survives_a_round_trip(store):
    assert store.selected() == "default"
    store.add("staging")
    store.select("staging")
    assert store.selected() == "staging"


def test_selecting_an_unknown_profile_is_refused(store):
    with pytest.raises(ProfileError, match="no such profile"):
        store.select("ghost")


def test_removing_an_unrelated_profile_leaves_the_selection_alone(store):
    store.add("default")
    store.add("staging")
    store.select("staging")
    store.remove("default")
    assert store.selected() == "staging"


def test_removing_the_selected_profile_clears_the_selection(store):
    store.add("staging")
    store.select("staging")
    store.remove("staging")
    assert store.selected() == "default"


# ------------------------------------------------------------------ #
# secrets                                                             #
# ------------------------------------------------------------------ #

def test_an_encoded_secret_round_trips_and_never_shows_its_value():
    stored = encode("sk-svcacct-ABCDE")
    assert "sk-svcacct-ABCDE" not in stored
    assert decode(stored, "OPENAI_API_KEY") == "sk-svcacct-ABCDE"
    assert display(stored) == "***"


def test_a_reference_is_stored_verbatim_and_resolved_from_the_environment(monkeypatch):
    stored = encode("$MY_KEY")
    assert stored == "$MY_KEY"
    monkeypatch.setenv("MY_KEY", "sk-live")
    assert decode(stored, "OPENAI_API_KEY") == "sk-live"
    assert display(stored) == "$MY_KEY (set)"


def test_an_unset_reference_reports_which_variable_is_missing(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    assert decode("$MY_KEY", "OPENAI_API_KEY") is None
    assert display("$MY_KEY") == "$MY_KEY (unset)"


def test_a_hand_written_unencoded_secret_still_works():
    """The file is documented as human-editable, so a pasted value must not break."""
    assert decode("sk-typed-by-hand", "OPENAI_API_KEY") == "sk-typed-by-hand"


# ------------------------------------------------------------------ #
# precedence                                                          #
# ------------------------------------------------------------------ #

def test_precedence_override_beats_environment_beats_profile_beats_default(spec, store):
    store.add("default", {"BLUE_DATA_LLM_MODEL": "from-profile"})
    r = resolver(spec, store, {"BLUE_DATA_LLM_MODEL": "from-env"})
    assert r.get("BLUE_DATA_LLM_MODEL", override="from-option") == "from-option"
    assert r.get("BLUE_DATA_LLM_MODEL") == "from-env"

    r2 = resolver(spec, store)
    assert r2.get("BLUE_DATA_LLM_MODEL") == "from-profile"

    store.remove("default")
    store.add("default")
    assert resolver(spec, store).get("BLUE_DATA_LLM_MODEL") == "gpt-4o"


def test_an_exported_variable_outranks_a_profile_reference_to_one(spec, store, monkeypatch):
    """Both read the environment, but a directly exported value is tier 2 and the
    profile's reference is tier 3."""
    store.add("default", {"OPENAI_API_KEY": "$FALLBACK_KEY"})
    monkeypatch.setenv("FALLBACK_KEY", "from-reference")
    r = resolver(spec, store, {"OPENAI_API_KEY": "from-env", "FALLBACK_KEY": "from-reference"})
    assert r.get("OPENAI_API_KEY") == "from-env"


def test_a_profile_reference_resolves_when_nothing_is_exported_directly(spec, store):
    store.add("default", {"OPENAI_API_KEY": "$FALLBACK_KEY"})
    r = resolver(spec, store, {"FALLBACK_KEY": "from-reference"})
    assert r.get("OPENAI_API_KEY") == "from-reference"


def test_an_unset_reference_falls_through_rather_than_resolving_to_nothing(spec, store):
    store.add("default", {"OPENAI_API_KEY": "$NOT_SET"})
    assert resolver(spec, store, {}).get("OPENAI_API_KEY") is None


def test_the_profile_used_is_the_selected_one(spec, store):
    store.add("default", {"BLUE_DATA_LLM_MODEL": "a"})
    store.add("staging", {"BLUE_DATA_LLM_MODEL": "b"})
    store.select("staging")
    assert resolver(spec, store).get("BLUE_DATA_LLM_MODEL") == "b"


def test_an_explicit_profile_overrides_the_selection(spec, store):
    store.add("default", {"BLUE_DATA_LLM_MODEL": "a"})
    store.add("staging", {"BLUE_DATA_LLM_MODEL": "b"})
    store.select("staging")
    assert resolver(spec, store, profile="default").get("BLUE_DATA_LLM_MODEL") == "a"


def test_resolution_works_before_any_profile_exists(spec, store):
    """A fresh install must not require `profile add` before the CLI runs."""
    assert resolver(spec, store).get("BLUE_DATA_LLM_MODEL") == "gpt-4o"


# ------------------------------------------------------------------ #
# inheritance                                                         #
# ------------------------------------------------------------------ #

def test_a_specific_model_falls_back_through_its_inheritance_chain(spec, store):
    store.add("default")
    assert resolver(spec, store).get("APP_EXTRACTION_LLM_MODEL") == "gpt-4o"

    store.set_value("default", "APP_LLM_MODEL", "app-wide")
    assert resolver(spec, store).get("APP_EXTRACTION_LLM_MODEL") == "app-wide"

    store.set_value("default", "APP_EXTRACTION_LLM_MODEL", "extraction-only")
    assert resolver(spec, store).get("APP_EXTRACTION_LLM_MODEL") == "extraction-only"
    assert resolver(spec, store).get("APP_LLM_MODEL") == "app-wide"


def test_an_exported_general_model_beats_a_profile_specific_one(spec, store):
    """Inheritance is consulted within a tier, so the whole environment tier
    outranks the whole profile tier."""
    store.add("default", {"APP_EXTRACTION_LLM_MODEL": "from-profile"})
    r = resolver(spec, store, {"BLUE_DATA_LLM_MODEL": "from-env"})
    assert r.get("APP_EXTRACTION_LLM_MODEL") == "from-env"


# ------------------------------------------------------------------ #
# reporting + export                                                  #
# ------------------------------------------------------------------ #

def test_source_of_traces_a_value_to_the_tier_that_set_it(spec, store):
    store.add("default", {"APP_WORKERS": "4"})
    r = resolver(spec, store, {"APP_DEBUG": "true"})
    assert r.source_of("APP_DEBUG") == "environment"
    assert r.source_of("APP_WORKERS") == "profile:default"
    assert r.source_of("BLUE_DATA_LLM_MODEL") == "default"
    assert r.source_of("OPENAI_API_KEY") == "unset"


def test_require_names_how_to_fix_a_missing_value(spec, store):
    with pytest.raises(ConfigError, match="profile config OPENAI_API_KEY"):
        resolver(spec, store).require("OPENAI_API_KEY")


def test_export_writes_resolved_values_into_the_environment(spec, store):
    store.add("default", {"OPENAI_API_KEY": encode("sk-abc"), "APP_WORKERS": "4"})
    env: dict[str, str] = {}
    r = ConfigResolver(spec, store, environ=env)
    r.export()
    assert env["OPENAI_API_KEY"] == "sk-abc"
    assert env["APP_WORKERS"] == "4"
    assert env["BLUE_DATA_LLM_MODEL"] == "gpt-4o"


def test_export_leaves_an_already_exported_variable_alone(spec, store):
    store.add("default", {"BLUE_DATA_LLM_MODEL": "from-profile"})
    env = {"BLUE_DATA_LLM_MODEL": "from-env"}
    ConfigResolver(spec, store, environ=env).export()
    assert env["BLUE_DATA_LLM_MODEL"] == "from-env"


def test_build_resolver_takes_a_home_directory(spec, tmp_path):
    r = build_resolver(spec, str(tmp_path / "home"), environ={})
    assert r.get("BLUE_DATA_LLM_MODEL") == "gpt-4o"
