"""Type aliases, walk options and the argument checks shared by the public calls."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ErrorHandler = Callable[[OSError], None]
OnError = Literal["raise", "ignore"] | ErrorHandler
"""An error policy: raise, ignore, or call a handler with each filesystem error.

>>> from dirsize import OnError
>>> errors: list[OSError] = []
>>> policy: OnError = errors.append
>>> policy(OSError("read failed"))
>>> len(errors)
1
"""

PathLike = str | os.PathLike[str]
ErrorKind = Literal["permission", "missing", "cycle", "other"]
"""The classification stored in ScanError.kind.

>>> from dirsize import ErrorKind, ScanError
>>> kind: ErrorKind = ScanError.from_os_error(FileNotFoundError(2, "gone")).kind
>>> kind
'missing'
"""

Measure = Literal["disk", "apparent"]
"""The byte total selected by a result's size method or by largest.

>>> from dirsize import Measure, FileUsage
>>> measure: Measure = "apparent"
>>> FileUsage("file", 3, 4096).size(measure)
3
"""

Kind = Literal["file", "dir"]


@dataclass(frozen=True)
class WalkOptions:
    """Internal walk switches; the public functions expose them as keyword arguments."""

    follow_symlinks: bool = False
    one_filesystem: bool = False
    count_links: bool = False
    include_dirs: bool = False
    report_cycles: bool = True


def check_path(path: object) -> str:
    """Return ``path`` as text; bytes paths and other objects raise ``TypeError``."""
    try:
        name = os.fspath(path) if isinstance(path, os.PathLike) else path
    except TypeError:
        raise TypeError("path must be a str or os.PathLike[str]") from None
    if not isinstance(name, str):
        raise TypeError("path must be a str or os.PathLike[str]")
    name = str.__str__(name)
    if chr(0) in name:
        raise ValueError("path must not contain a NUL character")
    if sys.platform == "win32" and (
        len(name) > 32767 or len(name.encode("utf-16-le", "surrogatepass")) > 65534
    ):
        raise ValueError("path is too long for Windows (maximum 32767 UTF-16 code units)")
    return name


def check_measure(by: object) -> Measure:
    """Return ``by`` when it names a measure, else raise ``ValueError``."""
    return "disk" if _choice(by, "by", ("disk", "apparent")) == "disk" else "apparent"


def check_kind(kind: object) -> Kind:
    """Return ``kind`` when it is ``"file"`` or ``"dir"``, else raise ``ValueError``."""
    return "file" if _choice(kind, "kind", ("file", "dir")) == "file" else "dir"


def _choice(value: object, name: str, choices: tuple[str, str]) -> str:
    # The text itself is compared, so a str subclass cannot redefine what matches.
    if isinstance(value, str) and str.__str__(value) in choices:
        return str.__str__(value)
    first, second = choices
    raise ValueError(f"{name} must be {first!r} or {second!r}")


def check_count(n: object) -> int:
    """Return ``n`` when it is an ``int`` of zero or more."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an int")
    count = int.__index__(n)  # the value itself, whatever an int subclass overrides
    if count < 0:
        raise ValueError("n must be zero or more")
    return count
