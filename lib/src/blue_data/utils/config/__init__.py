"""Profile-driven configuration shared by the Blue CLI family.

A CLI declares its parameters in a JSON spec, merges them with the family-wide
`base_spec()`, and resolves them through a `ConfigResolver` against the selected
profile in `~/.<cli>/.profiles`.

This package is deliberately free of any CLI framework: it decides *what* to
ask for and *what a value resolves to*, while prompting and command wiring stay
in each CLI. That keeps `blue-data`'s dependencies unchanged.
"""
from .profiles import DEFAULT_PROFILE, ProfileError, ProfileStore
from .resolve import ConfigResolver, build_resolver
from .secrets import MASK, SecretError, decode, display, encode, is_reference, reference_variable
from .spec import CASTS, ConfigError, ConfigSpec, ParamSpec, base_spec, load_spec, spec_from_dict

__all__ = [
    "CASTS",
    "DEFAULT_PROFILE",
    "MASK",
    "ConfigError",
    "ConfigResolver",
    "ConfigSpec",
    "ParamSpec",
    "ProfileError",
    "ProfileStore",
    "SecretError",
    "base_spec",
    "build_resolver",
    "decode",
    "display",
    "encode",
    "is_reference",
    "load_spec",
    "reference_variable",
    "spec_from_dict",
]
