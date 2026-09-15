"""Storage and display of secret configuration values.

Two forms, both written by a `cast: "secret"` parameter:

  OPENAI_API_KEY = enc:c2stc3ZjYWNjdC1BQkNERQ==   an encoded literal
  OPENAI_API_KEY = $OPENAI_API_KEY                 a reference to an env var

**The encoding is obfuscation, not encryption.** It keeps a key from being
readable over a shoulder or turning up in a careless `grep`, and it does
nothing else — anyone who can read the file can decode it. The protection that
matters is the 0600 mode `profiles.py` sets on the file. Where a secret needs
real protection, the reference form is the answer: the value then lives in the
environment and never touches disk.
"""
from __future__ import annotations

import base64
import os

_ENCODED_PREFIX = "enc:"
_REFERENCE_PREFIX = "$"

MASK = "***"


class SecretError(Exception):
    """A secret that cannot be resolved — usually an unset referenced variable."""


def is_reference(stored: str) -> bool:
    return stored.startswith(_REFERENCE_PREFIX)


def reference_variable(stored: str) -> str:
    """The environment variable name a reference points at."""
    return stored[len(_REFERENCE_PREFIX):]


def encode(value: str) -> str:
    """Encode a literal secret for storage. A `$VAR` reference is stored as-is."""
    if is_reference(value):
        return value
    return _ENCODED_PREFIX + base64.b64encode(value.encode()).decode()


def decode(stored: str, name: str, environ: dict[str, str] | None = None) -> str | None:
    """The usable secret behind a stored value.

    Returns None when a reference points at a variable that isn't set — the
    caller decides whether that is an error, since an optional secret being
    absent is perfectly normal. `environ` is injectable so a resolver working
    against a supplied environment stays consistent all the way down.
    """
    env = os.environ if environ is None else environ
    if is_reference(stored):
        return env.get(reference_variable(stored)) or None
    if stored.startswith(_ENCODED_PREFIX):
        payload = stored[len(_ENCODED_PREFIX):]
        try:
            return base64.b64decode(payload.encode()).decode()
        except Exception:
            raise SecretError(
                f"{name}: stored secret is not valid encoded data. "
                f"Re-set it with `profile config {name}`."
            ) from None
    # A value written by hand into the file, unencoded. Honor it rather than
    # failing — the file is meant to be human-editable.
    return stored or None


def display(stored: str, environ: dict[str, str] | None = None) -> str:
    """How a stored secret should appear in `inspect` and other output.

    A reference shows the variable name and whether it resolves: that tells the
    user what to export without revealing anything. A literal is masked, always
    in full — a partially revealed key is still a leaked key.
    """
    if is_reference(stored):
        env = os.environ if environ is None else environ
        var = reference_variable(stored)
        state = "set" if env.get(var) else "unset"
        return f"${var} ({state})"
    return MASK
