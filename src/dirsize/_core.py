"""Walk a directory tree once and total its size or count its files."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Literal

ErrorHandler = Callable[[OSError], None]
OnError = Literal["raise", "ignore"] | ErrorHandler
PathLike = str | os.PathLike[str]


def _raise(error: OSError) -> None:
    raise error


def _ignore(error: OSError) -> None:
    return None


def _as_handler(on_error: OnError) -> ErrorHandler:
    if callable(on_error):
        return on_error
    if on_error == "raise":
        return _raise
    if on_error == "ignore":
        return _ignore
    raise ValueError(f"on_error must be 'raise', 'ignore' or a callable, got {on_error!r}")


def _measure(
    root: PathLike,
    *,
    follow_symlinks: bool,
    on_error: OnError,
    want_size: bool,
) -> int:
    handle = _as_handler(on_error)
    total = 0
    seen_files: set[tuple[int, int]] = set()
    seen_dirs: set[tuple[int, int]] = set()

    start = os.fspath(root)
    if follow_symlinks:
        try:
            root_stat = os.stat(start)
            seen_dirs.add((root_stat.st_dev, root_stat.st_ino))
        except OSError as error:
            handle(error)

    stack: list[str] = [start]
    while stack:
        current = stack.pop()
        try:
            iterator = os.scandir(current)
        except OSError as error:
            handle(error)
            continue
        with iterator:
            for entry in iterator:
                total += _visit(
                    entry,
                    stack,
                    seen_files,
                    seen_dirs,
                    follow_symlinks=follow_symlinks,
                    handle=handle,
                    want_size=want_size,
                )
    return total


def _visit(
    entry: os.DirEntry[str],
    stack: list[str],
    seen_files: set[tuple[int, int]],
    seen_dirs: set[tuple[int, int]],
    *,
    follow_symlinks: bool,
    handle: ErrorHandler,
    want_size: bool,
) -> int:
    try:
        is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
        stat = os.stat(entry.path, follow_symlinks=follow_symlinks)
    except OSError as error:
        handle(error)
        return 0

    if is_dir:
        if follow_symlinks:
            key = (stat.st_dev, stat.st_ino)
            if key in seen_dirs:
                return 0
            seen_dirs.add(key)
        stack.append(entry.path)
        return 0

    if not want_size:
        return 1

    if stat.st_nlink > 1 and stat.st_ino != 0:
        key = (stat.st_dev, stat.st_ino)
        if key in seen_files:
            return 0
        seen_files.add(key)
    return stat.st_size


def dir_size(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the total size in bytes of every file under ``path``.

    Hardlinked files are counted once. Symlinked directories are not descended
    unless ``follow_symlinks`` is true, in which case loops are detected and
    skipped. ``on_error`` is ``"raise"``, ``"ignore"`` or a callable that
    receives each :class:`OSError`.
    """
    return _measure(path, follow_symlinks=follow_symlinks, on_error=on_error, want_size=True)


def file_count(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the number of files under ``path``, one per directory entry."""
    return _measure(path, follow_symlinks=follow_symlinks, on_error=on_error, want_size=False)
