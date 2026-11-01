"""The ``n`` largest files or directories of a tree, with bounded memory."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from operator import attrgetter
from typing import Literal, overload

from ._errors import as_handler
from ._results import DirUsage, FileUsage
from ._types import (
    Kind,
    Measure,
    OnError,
    PathLike,
    WalkOptions,
    check_count,
    check_kind,
    check_measure,
    check_path,
)
from ._walk import walk


@overload
def largest(
    path: PathLike,
    n: int = 10,
    *,
    by: Measure = "disk",
    kind: Literal["file"] = "file",
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    on_error: OnError = "ignore",
) -> list[FileUsage]: ...


@overload
def largest(
    path: PathLike,
    n: int = 10,
    *,
    by: Measure = "disk",
    kind: Literal["dir"],
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    on_error: OnError = "ignore",
) -> list[DirUsage]: ...


def largest(
    path: PathLike,
    n: int = 10,
    *,
    by: Measure = "disk",
    kind: Kind = "file",
    follow_symlinks: bool = False,
    one_filesystem: bool = False,
    count_links: bool = False,
    on_error: OnError = "ignore",
) -> list[FileUsage] | list[DirUsage]:
    """Return the ``n`` largest files (or directories with ``kind="dir"``), biggest first.

    ``by`` picks ``"disk"`` or ``"apparent"`` bytes. Ties keep walk order. A
    directory's size includes everything below it. Only ``n`` items are held. A
    second name of a hard-linked file weighs 0 unless ``count_links``. Other
    options mean what they mean in :func:`scan`; directories never include their
    own blocks here. ``n`` must be an ``int`` of zero or more.
    A regular-file root with ``kind="dir"`` produces a synthetic ``DirUsage``
    with its bytes, ``files=1``, ``dirs=0`` and ``depth=0``. With ``n=0``,
    arguments are validated but the filesystem is not read.

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     for name, size in [("a.txt", 10), ("b.txt", 300), ("c.txt", 20)]:
    ...         _ = pathlib.Path(tmp, name).write_bytes(b"x" * size)
    ...     top = largest(tmp, 2, by="apparent")
    >>> [(pathlib.Path(item.path).name, item.apparent_bytes) for item in top]
    [('b.txt', 300), ('c.txt', 20)]
    """
    count, measure, want = check_count(n), check_measure(by), check_kind(kind)
    name, handle = check_path(path), as_handler(on_error)
    options = WalkOptions(follow_symlinks, one_filesystem, count_links)
    found = top_items(walk(name, options, handle), count, measure, want)
    if want == "file":
        return [item for item in found if isinstance(item, FileUsage)]
    return [item for item in found if isinstance(item, DirUsage)]


def top_items(
    items: Iterable[FileUsage | DirUsage], n: int, by: Measure, kind: Kind
) -> list[FileUsage | DirUsage]:
    """Keep the ``n`` biggest items of one kind, biggest first, ties in arrival order."""
    want = FileUsage if kind == "file" else DirUsage
    size = attrgetter("disk_bytes" if by == "disk" else "apparent_bytes")
    ranked = (
        (size(item), -order, item) for order, item in enumerate(items) if isinstance(item, want)
    )
    return [entry[2] for entry in heapq.nlargest(n, ranked, key=lambda e: (e[0], e[1]))]
