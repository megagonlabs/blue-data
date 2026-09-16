"""Declarative configuration parameters, and the casts that validate them.

A *spec* describes the configuration a CLI accepts: one entry per parameter,
keyed by the environment-variable name it resolves to. Specs compose — this
package ships the family-wide parameters (`base_spec.json`) and each CLI adds
its own, so `BLUE_DATA_LLM_MODEL` is declared once for everyone while
`BLUE_DATA_KB_SOURCE_DATA_DIR` belongs to one repo.

    {
      "BLUE_DATA_LLM_MODEL": {
        "default": "gpt-4o",
        "prompt": "Default LLM model",
        "required": true,
        "cast": "str"
      }
    }

`required` selects what an interactive walkthrough asks about; everything else
is set one parameter at a time. `cast` both validates input and converts it.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CASTS = ("directory", "file", "str", "int", "float", "bool", "secret")

_TRUE = ("1", "true", "yes", "y", "on")
_FALSE = ("0", "false", "no", "n", "off")

_BASE_SPEC_PATH = Path(__file__).with_name("base_spec.json")


class ConfigError(Exception):
    """Invalid configuration, or a value that does not satisfy its cast."""


@dataclass(frozen=True)
class ParamSpec:
    """One declared configuration parameter."""

    name: str
    default: Any = None
    prompt: str = ""
    required: bool = False
    cast: str = "str"
    inherits: tuple[str, ...] = ()

    @property
    def is_secret(self) -> bool:
        return self.cast == "secret"

    def cast_value(self, value: Any) -> Any:
        """Validate and convert *value* according to this parameter's cast.

        Raises ConfigError with a message naming the parameter, so a bad value
        from a prompt, a profile file, or the environment all report the same way.
        """
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        try:
            return _CASTERS[self.cast](text)
        except KeyError:
            raise ConfigError(f"{self.name}: unknown cast {self.cast!r}") from None
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"{self.name}: {exc}") from None


def _cast_directory(text: str) -> str:
    return str(Path(text).expanduser())


def _cast_file(text: str) -> str:
    return str(Path(text).expanduser())


def _cast_bool(text: str) -> bool:
    low = text.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    raise ConfigError(f"expected a boolean, got {text!r}")


_CASTERS = {
    "directory": _cast_directory,
    "file": _cast_file,
    "str": str,
    "int": int,
    "float": float,
    "bool": _cast_bool,
    # Secrets are stored encoded and resolved elsewhere (see secrets.py); as a
    # value they are just text.
    "secret": str,
}


class ConfigSpec:
    """An ordered collection of ParamSpec, keyed by parameter name."""

    def __init__(self, params: dict[str, ParamSpec] | None = None) -> None:
        self._params: dict[str, ParamSpec] = dict(params or {})

    def __contains__(self, name: object) -> bool:
        return name in self._params

    def __getitem__(self, name: str) -> ParamSpec:
        try:
            return self._params[name]
        except KeyError:
            raise ConfigError(
                f"unknown configuration parameter {name!r}. "
                f"Known parameters: {', '.join(sorted(self._params)) or '(none)'}"
            ) from None

    def __iter__(self) -> Iterator[ParamSpec]:
        return iter(self._params.values())

    def __len__(self) -> int:
        return len(self._params)

    def get(self, name: str) -> ParamSpec | None:
        return self._params.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._params)

    def required(self) -> list[ParamSpec]:
        """The parameters an interactive walkthrough should ask about."""
        return [p for p in self._params.values() if p.required]

    def merged_with(self, other: ConfigSpec) -> ConfigSpec:
        """This spec plus *other*; `other` wins on a name collision, so a CLI can
        refine a family-wide parameter (a different default, say) without
        redeclaring the rest."""
        return ConfigSpec({**self._params, **other._params})


def spec_from_dict(raw: dict[str, Any]) -> ConfigSpec:
    params: dict[str, ParamSpec] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"{name}: spec entry must be an object, got {type(entry).__name__}")
        cast = entry.get("cast", "str")
        if cast not in CASTS:
            raise ConfigError(f"{name}: unknown cast {cast!r}; expected one of {', '.join(CASTS)}")
        inherits = entry.get("inherits") or ()
        if isinstance(inherits, str):
            inherits = (inherits,)
        params[name] = ParamSpec(
            name=name,
            default=entry.get("default"),
            prompt=entry.get("prompt", ""),
            required=bool(entry.get("required", False)),
            cast=cast,
            inherits=tuple(inherits),
        )
    return ConfigSpec(params)


def load_spec(path: str | Path) -> ConfigSpec:
    data = json.loads(Path(path).read_text())
    return spec_from_dict(data)


def base_spec() -> ConfigSpec:
    """The family-wide parameters every Blue CLI shares."""
    return load_spec(_BASE_SPEC_PATH)
