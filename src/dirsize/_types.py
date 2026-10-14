"""Typed results and the error policy shared by every walk."""

from __future__ import annotations

import errno
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

ErrorHandler = Callable[[OSError], None]
OnError = Literal["raise", "ignore"] | ErrorHandler
PathLike = str | os.PathLike[str]
ErrorKind = Literal["permission", "missing", "cycle", "other"]
Measure = Literal["disk", "apparent"]


@dataclass(frozen=True)
class ScanError:
    """One path that could not be measured, and why.

    ``kind`` is ``"permission"``, ``"missing"`` (vanished or not a directory),
    ``"cycle"`` (a directory that contains itself, without following links) or
    ``"other"``.
    """

    path: str
    kind: ErrorKind
    message: str

    @classmethod
    def from_os_error(cls, error: OSError) -> ScanError:
        """Classify ``error`` and keep its path and message."""
        return cls(path=_error_path(error), kind=_kind(error), message=error.strerror or str(error))


@dataclass(frozen=True)
class FileUsage:
    """Size of one non-directory entry (a file, a link that was not followed, a device)."""

    path: str
    apparent_bytes: int
    disk_bytes: int
    is_link: bool = False


@dataclass(frozen=True)
class DirUsage:
    """Totals for one directory and everything below it.

    ``files`` counts every non-directory entry, one per name. A file with several
    hard links adds its bytes once unless ``count_links`` was set. ``links`` is the
    number of those entries that are links left unfollowed. ``dirs`` counts the
    directories entered below this one. ``errors`` counts the errors met inside.
    """

    path: str
    apparent_bytes: int
    disk_bytes: int
    files: int
    dirs: int
    links: int
    errors: int
    depth: int

    def size(self, by: Measure = "disk") -> int:
        """Return ``disk_bytes`` or ``apparent_bytes``."""
        return self.disk_bytes if by == "disk" else self.apparent_bytes


@dataclass(frozen=True)
class Usage:
    """Result of :func:`dirsize.scan`: the totals for one path plus every error met.

    ``measured`` is false when ``path`` itself could not be read; the totals are then 0.
    """

    path: str
    apparent_bytes: int
    disk_bytes: int
    files: int
    dirs: int
    links: int
    errors: tuple[ScanError, ...] = field(default=())
    measured: bool = True

    @property
    def ok(self) -> bool:
        """True when the whole tree was measured without a single error."""
        return not self.errors


@dataclass(frozen=True)
class WalkOptions:
    """Internal walk switches; the public functions expose them as keyword arguments."""

    follow_symlinks: bool = False
    one_filesystem: bool = False
    count_links: bool = False
    include_dirs: bool = False
    report_cycles: bool = True


def as_handler(on_error: OnError) -> ErrorHandler:
    """Turn the public ``on_error`` value into a callable, rejecting anything else."""
    if callable(on_error):
        return on_error
    if on_error == "raise":
        return _raise
    if on_error == "ignore":
        return _ignore
    raise ValueError(f"on_error must be 'raise', 'ignore' or a callable, got {on_error!r}")


def cycle_error(path: str) -> OSError:
    """Build the error reported when a followed link points back to an ancestor."""
    return OSError(errno.ELOOP, "circular directory structure", path)


def _raise(error: OSError) -> None:
    raise error


def _ignore(error: OSError) -> None:
    return None


def _error_path(error: OSError) -> str:
    name = error.filename
    if isinstance(name, bytes):
        return os.fsdecode(name)
    return "" if name is None else str(name)


def _kind(error: OSError) -> ErrorKind:
    if isinstance(error, PermissionError):
        return "permission"
    if isinstance(error, (FileNotFoundError, NotADirectoryError)):
        return "missing"
    if error.errno == errno.ELOOP:
        return "cycle"
    return "other"
