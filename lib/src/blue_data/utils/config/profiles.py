"""The `.profiles` file: named sets of configuration, and the selected one.

    ~/.<cli>/.profiles          INI sections, one per profile   (0600)
    ~/.<cli>/.selected.profile  the profile in use

    [default]
    BLUE_DATA_LLM_MODEL = gpt-4o
    OPENAI_API_KEY = enc:c2stc3ZjYWNjdC1BQkNERQ==

    [staging]
    OPENAI_API_KEY = $OPENAI_API_KEY

The file is meant to be readable and editable by hand, which is why it is INI
rather than JSON, and why an unencoded secret typed in directly still works.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

DEFAULT_PROFILE = "default"

_PROFILES_FILE = ".profiles"
_SELECTED_FILE = ".selected.profile"

_FILE_MODE = 0o600
_DIR_MODE = 0o700


class ProfileError(Exception):
    """A missing profile, or one that cannot be created or removed."""


class ProfileStore:
    """Read/write access to one CLI's profiles, rooted at its home directory."""

    def __init__(self, home: str | Path) -> None:
        self.home = Path(home).expanduser()

    # -------------------------------------------------------------- #
    # paths                                                           #
    # -------------------------------------------------------------- #

    @property
    def profiles_path(self) -> Path:
        return self.home / _PROFILES_FILE

    @property
    def selected_path(self) -> Path:
        return self.home / _SELECTED_FILE

    # -------------------------------------------------------------- #
    # file I/O                                                        #
    # -------------------------------------------------------------- #

    def _parser(self) -> configparser.ConfigParser:
        # optionxform=str keeps KEYS uppercase (the default lowercases them, and
        # these keys are environment-variable names). interpolation=None stops
        # configparser reading a '%' inside a secret as a format directive.
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str        # type: ignore[assignment,method-assign]
        if self.profiles_path.exists():
            parser.read(self.profiles_path)
        return parser

    def _write(self, parser: configparser.ConfigParser) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, _DIR_MODE)
        except OSError:
            pass                        # a shared or exotic filesystem; keep going
        with open(self.profiles_path, "w") as fh:
            parser.write(fh)
        try:
            os.chmod(self.profiles_path, _FILE_MODE)
        except OSError:
            pass

    # -------------------------------------------------------------- #
    # profiles                                                        #
    # -------------------------------------------------------------- #

    def list_profiles(self) -> list[str]:
        return list(self._parser().sections())

    def exists(self, name: str) -> bool:
        return self._parser().has_section(name)

    def add(self, name: str, values: dict[str, str] | None = None) -> None:
        parser = self._parser()
        if parser.has_section(name):
            raise ProfileError(f"profile {name!r} already exists")
        parser.add_section(name)
        for key, value in (values or {}).items():
            parser.set(name, key, str(value))
        self._write(parser)

    def remove(self, name: str) -> None:
        parser = self._parser()
        if not parser.remove_section(name):
            raise ProfileError(f"no such profile: {name!r}")
        self._write(parser)
        # Only clear the selection if it pointed at this profile — removing one
        # profile must not disturb an unrelated selection.
        if self.selected() == name and self.selected_path.exists():
            self.selected_path.unlink()

    def values(self, name: str) -> dict[str, str]:
        """Raw stored values for *name* — secrets still encoded."""
        parser = self._parser()
        if not parser.has_section(name):
            raise ProfileError(f"no such profile: {name!r}")
        return dict(parser.items(name))

    def set_value(self, name: str, key: str, value: str) -> None:
        parser = self._parser()
        if not parser.has_section(name):
            raise ProfileError(f"no such profile: {name!r}")
        parser.set(name, key, str(value))
        self._write(parser)

    def unset_value(self, name: str, key: str) -> None:
        parser = self._parser()
        if parser.has_section(name):
            parser.remove_option(name, key)
            self._write(parser)

    # -------------------------------------------------------------- #
    # selection                                                       #
    # -------------------------------------------------------------- #

    def selected(self) -> str:
        if self.selected_path.exists():
            name = self.selected_path.read_text().strip()
            if name:
                return name
        return DEFAULT_PROFILE

    def select(self, name: str) -> None:
        if not self.exists(name):
            raise ProfileError(
                f"no such profile: {name!r}. Create it with `profile add {name}`."
            )
        self.home.mkdir(parents=True, exist_ok=True)
        self.selected_path.write_text(name)
