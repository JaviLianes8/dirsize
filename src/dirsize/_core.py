"""The public measuring functions, all thin layers over one walk."""

from __future__ import annotations

import heapq
import os
from collections.abc import Iterator
from typing import Literal

from ._types import (
    DirUsage,
    ErrorHandler,
    FileUsage,
    Measure,
    OnError,
    PathLike,
    ScanError,
    Usage,
    WalkOptions,
    as_handler,
)
from ._walk import Seen, walk


def _items(path: PathLike, handle: ErrorHandler, **options: bool) -> Iterator[FileUsage | DirUsage]:
    return walk(os.fspath(path), WalkOptions(**options), handle)


def scan(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    include_dirs: bool = False,
    on_error: OnError = "ignore",
) -> Usage:
    """Measure the tree at ``path`` and return its totals with every error met.

    ``disk_bytes`` is the space allocated (``st_blocks`` on POSIX, compressed or
    sparse aware NTFS allocation on Windows); ``apparent_bytes`` is the sum of
    ``st_size``. A file with several hard links counts once unless ``count_links``.
    Symlinks and Windows junctions below ``path`` are counted as links and not
    entered unless ``follow_symlinks``; ``path`` itself is always resolved.
    ``one_filesystem`` skips directories on another device, like ``du -x``.
    ``include_dirs`` adds the blocks each directory takes, as ``du`` does.
    Errors are collected in :attr:`Usage.errors`; ``on_error="raise"`` stops at
    the first one and a callable also sees each :class:`OSError` as it happens.
    """
    options = WalkOptions(follow_symlinks, one_filesystem, count_links, include_dirs)
    return measure(path, options, as_handler(on_error), Seen())


def measure(path: PathLike, options: WalkOptions, handle: ErrorHandler, seen: Seen) -> Usage:
    """Run :func:`scan` with a ``seen`` set shared with other roots (the CLI's arguments)."""
    errors: list[ScanError] = []

    def collect(error: OSError) -> None:
        errors.append(ScanError.from_os_error(error))
        handle(error)

    total: DirUsage | None = None
    for item in walk(os.fspath(path), options, collect, seen):
        if isinstance(item, DirUsage) and item.depth == 0:
            total = item
    name = os.fspath(path)
    if total is None:
        return Usage(name, 0, 0, 0, 0, 0, tuple(errors), measured=False)
    a, d = total.apparent_bytes, total.disk_bytes
    return Usage(name, a, d, total.files, total.dirs, total.links, tuple(errors))


def iter_dirs(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    include_dirs: bool = False,
    on_error: OnError = "ignore",
) -> Iterator[DirUsage]:
    """Yield a :class:`DirUsage` for every directory, children before their parent.

    The root comes last. Results stream while the walk goes on; memory holds the
    walk stack and the identities of directories and hard-linked files seen.
    Options mean what they mean in :func:`scan`.
    """
    items = _items(
        path,
        as_handler(on_error),
        follow_symlinks=follow_symlinks,
        one_filesystem=one_filesystem,
        count_links=count_links,
        include_dirs=include_dirs,
    )
    return (item for item in items if isinstance(item, DirUsage))


def largest(
    path: PathLike,
    n: int = 10,
    *,
    by: Measure = "disk",
    kind: Literal["file", "dir"] = "file",
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    on_error: OnError = "ignore",
) -> list[FileUsage] | list[DirUsage]:
    """Return the ``n`` largest files (or directories), biggest first.

    Ties keep walk order. ``by`` picks ``"disk"`` or ``"apparent"`` bytes. A
    directory's size includes everything below it. Only ``n`` items are held. A
    second name of a hard-linked file weighs 0 unless ``count_links``.
    """
    if n < 0:
        raise ValueError(f"n must be zero or more, got {n}")
    if by not in ("disk", "apparent"):
        raise ValueError(f"by must be 'disk' or 'apparent', got {by!r}")
    if kind not in ("file", "dir"):
        raise ValueError(f"kind must be 'file' or 'dir', got {kind!r}")
    want = FileUsage if kind == "file" else DirUsage
    items = (
        (_size(item, by), -order, item)
        for order, item in enumerate(
            _items(
                path,
                as_handler(on_error),
                follow_symlinks=follow_symlinks,
                one_filesystem=one_filesystem,
                count_links=count_links,
            )
        )
        if isinstance(item, want)
    )
    top = heapq.nlargest(n, items, key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in top]  # type: ignore[return-value]


def _size(item: FileUsage | DirUsage, by: Measure) -> int:
    return item.disk_bytes if by == "disk" else item.apparent_bytes


def dir_size(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the total size in bytes (apparent, ``st_size``) of every file under ``path``.

    Hardlinked files are counted once. Symlinked directories and Windows junctions
    are not descended unless ``follow_symlinks`` is true, in which case loops are
    detected and skipped. ``on_error`` is ``"raise"``, ``"ignore"`` or a callable
    that receives each :class:`OSError`.
    """
    handle = as_handler(on_error)
    return sum(
        item.apparent_bytes
        for item in _items(path, handle, follow_symlinks=follow_symlinks, report_cycles=False)
        if isinstance(item, FileUsage)
    )


def file_count(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the number of files under ``path``, one per directory entry."""
    handle = as_handler(on_error)
    items = _items(path, handle, follow_symlinks=follow_symlinks, report_cycles=False)
    return sum(1 for item in items if isinstance(item, FileUsage))
