"""Cross-process locking and crash-safe JSON writes for the file-backed stores (#124).

Unix-only: the lock is an exclusive ``fcntl.flock`` on a ``<file>.lock`` sidecar.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any


class FileLocks:
    """One exclusive lock per path, held across processes and threads.

    Reentrant within a thread: a locked call that makes another locked call on
    the same path doesn't deadlock on itself (flock is per open file, so a second
    open + flock in the same process would). The OS lock is taken only by the
    outermost holder; inner ones just count.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._threads: dict[str, threading.RLock] = {}
        self._depth: dict[str, int] = {}
        self._fds: dict[str, int] = {}

    @contextmanager
    def hold(self, path: str) -> Iterator[None]:
        with self._guard:
            rlock = self._threads.setdefault(path, threading.RLock())
        with rlock:
            depth = self._depth.get(path, 0)
            if depth == 0:
                fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                except BaseException:
                    os.close(fd)
                    raise
                self._fds[path] = fd
            self._depth[path] = depth + 1
            try:
                yield
            finally:
                self._depth[path] -= 1
                if self._depth[path] == 0:
                    fd = self._fds.pop(path)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    finally:
                        os.close(fd)


# Shared by every store in the process, so two instances on one file serialize
# with each other and nest without deadlocking.
_LOCKS = FileLocks()


def file_lock(path: str | os.PathLike) -> AbstractContextManager[None]:
    """Hold an exclusive lock on *path* (via its ``<path>.lock`` sidecar) for the ``with`` block."""
    return _LOCKS.hold(os.path.abspath(os.fspath(path)) + ".lock")


def write_json_atomic(
    path: str | os.PathLike, data: Any, mode: int | None = None, **dump_kwargs: Any
) -> None:
    """Serialize *data* to *path* without ever leaving a partial file behind.

    The JSON goes to a unique temp file in the same directory, then ``os.replace``
    swaps it in, so readers see either the old file or the new one. If
    serialization fails partway, the existing file is untouched. *mode* sets the
    file's permissions; by default it keeps the current file's mode, or what a
    plain ``open(path, "w")`` would give under the process umask.
    """
    path = os.fspath(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
        # mkstemp creates the file 0600; without this, saves would narrow a
        # group-shared data directory's files to their owner.
        os.chmod(tmp, _target_mode(path) if mode is None else mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _target_mode(path: str) -> int:
    try:
        return os.stat(path).st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask
