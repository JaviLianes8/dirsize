"""Type aliases, walk options and the argument checks shared by the public calls."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ErrorHandler = Callable[[OSError], None]
OnError = Literal["raise", "ignore"] | ErrorHandler
PathLike = str | os.PathLike[str]
ErrorKind = Literal["permission", "missing", "cycle", "other"]
Measure = Literal["disk", "apparent"]
Kind = Literal["file", "dir"]

# Error messages quote at most this many characters of a bad argument.
SHOWN = 40


@dataclass(frozen=True)
class WalkOptions:
    """Internal walk switches; the public functions expose them as keyword arguments."""

    follow_symlinks: bool = False
    one_filesystem: bool = False
    count_links: bool = False
    include_dirs: bool = False
    report_cycles: bool = True


def shown(value: object) -> str:
    """Describe ``value`` for an error message in at most ``SHOWN`` characters."""
    try:
        text = repr(value)
    except Exception:  # a huge int or a broken __repr__ must not hide the real error
        text = f"<{type(value).__name__}>"
    return text if len(text) <= SHOWN else text[: SHOWN - 3] + "..."


def check_path(path: object) -> str:
    """Return ``path`` as text; bytes paths and other objects raise ``TypeError``."""
    if isinstance(path, str):
        return path
    if isinstance(path, os.PathLike):
        name = os.fspath(path)
        if isinstance(name, str):
            return name
        kind = f"os.PathLike[{type(name).__name__}]"
    else:
        kind = type(path).__name__
    raise TypeError(f"path must be a str or os.PathLike[str], got {kind[:SHOWN]}")


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
    raise ValueError(f"{name} must be {first!r} or {second!r}, got {shown(value)}")


def check_count(n: object) -> int:
    """Return ``n`` when it is an ``int`` of zero or more."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"n must be an int, got {type(n).__name__[:SHOWN]}")
    count = int.__index__(n)  # the value itself, whatever an int subclass overrides
    if count < 0:
        raise ValueError("n must be zero or more")
    return count
