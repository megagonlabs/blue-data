from __future__ import annotations

import os
from pathlib import Path


def contain(root: str, name: str, suffix: str = "") -> str:
    """Resolve a caller-supplied *name* (plus optional *suffix*) to an absolute
    path strictly inside *root*, refusing path traversal.

    ``name`` must be a single path component: not empty, not absolute, not ``.``
    or ``..``, and free of path separators. The composed path is then resolved
    (following symlinks) and required to stay within the resolved *root*, so a
    symlink inside *root* that points elsewhere is rejected too.

    Returns the absolute path. Raises ``ValueError`` for an unsafe name.
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"unsafe path name: {name!r}")
    if os.path.isabs(name) or name in (os.curdir, os.pardir):
        raise ValueError(f"path name must be relative and not a dot reference: {name!r}")
    if os.sep in name or (os.altsep and os.altsep in name):
        raise ValueError(f"path name must be a single component, not a path: {name!r}")

    root_abs = Path(root).resolve()
    target = (root_abs / f"{name}{suffix}").resolve()
    if target == root_abs or not target.is_relative_to(root_abs):
        raise ValueError(f"path name escapes {root!r}: {name!r}")
    return str(target)
