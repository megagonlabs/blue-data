"""Resolving a configuration value, and exporting a profile to the environment.

Precedence, highest first:

  1. an explicit override   — a command-line option
  2. the real environment   — an exported variable
  3. the profile            — the selected section of `.profiles`
  4. the spec default

A profile value may itself be a `$VAR` reference. That resolves against the
environment but stays at tier 3: a variable exported directly still wins over a
profile that points at one, which is what makes `FOO=x cli ...` behave the way
anyone would expect.

Some parameters inherit: an unset `BLUE_DATA_KB_SOURCE_EXTRACTION_LLM_MODEL`
falls back to `BLUE_DATA_KB_SOURCE_LLM_MODEL`, then to `BLUE_DATA_LLM_MODEL`.
Inheritance is consulted per tier, not after it — a profile-level specific
value beats a profile-level general one, but an *exported* specific variable
beats both.
"""
from __future__ import annotations

import os
from typing import Any

from .profiles import DEFAULT_PROFILE, ProfileError, ProfileStore
from .secrets import decode
from .spec import ConfigError, ConfigSpec, ParamSpec


class ConfigResolver:
    """Resolves parameters for one CLI: its spec, its profiles, its environment."""

    def __init__(
        self,
        spec: ConfigSpec,
        store: ProfileStore,
        profile: str | None = None,
        environ: dict[str, str] | None = None,
    ) -> None:
        self.spec = spec
        self.store = store
        # Writes go to the live mapping; reads go to a snapshot taken now. A
        # resolver must not observe its own `export()` — otherwise every value
        # it wrote would report as coming from the environment, and a second
        # resolver built later in the same process would agree.
        self.environ = os.environ if environ is None else environ
        self._env = dict(self.environ)
        self.profile = profile or self._env.get("BLUE_DATA_PROFILE") or store.selected()
        self._values: dict[str, str] | None = None

    # -------------------------------------------------------------- #

    def profile_values(self) -> dict[str, str]:
        """Stored values for the active profile.

        A missing requested/selected profile is a configuration error and raises
        ProfileError — running silently against the environment and defaults hides
        a misspelled --profile/BLUE_DATA_PROFILE or a selection pointing at a
        renamed/removed profile (#88). The sole tolerated case is a fresh install
        where the profiles file has not been created yet: the default profile is
        allowed to be absent (ProfileStore.initialize() creates it)."""
        if self._values is None:
            if self.store.exists(self.profile):
                self._values = self.store.values(self.profile)
            elif self.profile == DEFAULT_PROFILE and not self.store.profiles_path.exists():
                self._values = {}
            else:
                raise ProfileError(f"no such profile: {self.profile!r}")
        return self._values

    # -------------------------------------------------------------- #

    def _chain(self, param: ParamSpec) -> list[ParamSpec]:
        """`param` followed by the parameters it inherits from, most specific first."""
        chain = [param]
        for name in param.inherits:
            inherited = self.spec.get(name)
            if inherited is not None and inherited not in chain:
                chain.append(inherited)
        return chain

    def _from_environ(self, chain: list[ParamSpec]) -> Any:
        for p in chain:
            raw = self._env.get(p.name)
            if raw:
                return p.cast_value(raw)
        return None

    def _from_profile(self, chain: list[ParamSpec]) -> Any:
        values = self.profile_values()
        for p in chain:
            stored = values.get(p.name)
            if not stored:
                continue
            if p.is_secret:
                secret = decode(stored, p.name, self._env)
                if secret:
                    return secret
                continue        # an unset $VAR reference: keep looking
            return p.cast_value(stored)
        return None

    def _from_default(self, chain: list[ParamSpec]) -> Any:
        for p in chain:
            if p.default is not None:
                return p.cast_value(p.default)
        return None

    def get(self, name: str, override: Any = None) -> Any:
        """The resolved value for *name*, or None."""
        param = self.spec[name]
        if override is not None:
            return param.cast_value(override)
        chain = self._chain(param)
        for tier in (self._from_environ, self._from_profile, self._from_default):
            value = tier(chain)
            if value is not None:
                return value
        return None

    def require(self, name: str) -> Any:
        """Like `get`, but raises with a message naming what to do about it."""
        value = self.get(name)
        if value is None:
            raise ConfigError(
                f"{name} is not configured. Set it with "
                f"`profile config {name}`, or export {name} in the environment."
            )
        return value

    def source_of(self, name: str) -> str:
        """Which tier a value came from — for `inspect`, so a surprising value can
        be traced to the thing that set it."""
        param = self.spec[name]
        chain = self._chain(param)
        if self._from_environ(chain) is not None:
            return "environment"
        if self._from_profile(chain) is not None:
            return f"profile:{self.profile}"
        if self._from_default(chain) is not None:
            return "default"
        return "unset"

    # -------------------------------------------------------------- #

    def export(self) -> dict[str, str]:
        """Resolve every parameter and write it into `os.environ`.

        This is the bridge to everything that already reads configuration from
        the environment — the OpenAI SDK, `blue_data.config`, Click's own
        `envvar=` options. A profile is a named set of environment variables, so
        applying one means setting them. Values already exported are left alone,
        since tier 2 outranks the profile.
        """
        applied: dict[str, str] = {}
        for param in self.spec:
            if self._env.get(param.name):
                continue
            value = self.get(param.name)
            if value is None:
                continue
            self.environ[param.name] = str(value)
            applied[param.name] = str(value)
        return applied


def build_resolver(
    spec: ConfigSpec,
    home: str,
    profile: str | None = None,
    environ: dict[str, str] | None = None,
) -> ConfigResolver:
    """Convenience constructor: spec + CLI home directory -> resolver."""
    return ConfigResolver(spec, ProfileStore(home), profile=profile, environ=environ)


__all__ = ["ConfigResolver", "build_resolver", "DEFAULT_PROFILE"]
