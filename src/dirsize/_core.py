"""The public measuring functions, all thin layers over one walk."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import closing

from ._errors import ScanError, as_handler
from ._results import DirUsage, FileUsage, Usage
from ._state import RootStatus, Seen
from ._types import ErrorHandler, OnError, PathLike, WalkOptions, check_path
from ._walk import walk


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

    ``disk_bytes`` is the space allocated (``st_blocks`` on POSIX, the NTFS
    allocation on Windows, aware of compression and sparse files);
    ``apparent_bytes`` is the sum of ``st_size``. A file with several hard links
    counts once unless ``count_links``. Symlinks and Windows junctions below
    ``path`` are counted as links and not entered unless ``follow_symlinks``;
    ``path`` itself is always resolved. ``one_filesystem`` skips directories on
    another device, like ``du -x``. ``include_dirs`` adds the blocks each
    directory takes, as ``du`` does. Errors are collected in :attr:`Usage.errors`;
    ``on_error="raise"`` stops at the first one and a callable also sees each
    :class:`OSError` as it happens (it may raise to stop the walk).

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = pathlib.Path(tmp, "a.txt").write_bytes(b"hello")
    ...     usage = scan(tmp)
    >>> usage.apparent_bytes, usage.files, usage.dirs, usage.ok
    (5, 1, 0, True)
    """
    options = WalkOptions(follow_symlinks, one_filesystem, count_links, include_dirs)
    return measure(check_path(path), options, as_handler(on_error), Seen())


def measure(name: str, options: WalkOptions, handle: ErrorHandler, seen: Seen) -> Usage:
    """Run :func:`scan` with a ``seen`` set shared with other roots (the CLI's arguments)."""
    errors: list[ScanError] = []

    def collect(error: OSError) -> None:
        errors.append(ScanError.from_os_error(error))
        handle(error)

    total: DirUsage | None = None
    status = RootStatus()
    for item in walk(name, options, collect, seen, status):
        if isinstance(item, DirUsage) and item.depth == 0:
            total = item
    if total is None or not status.measured:
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
) -> Generator[DirUsage, None, None]:
    """Yield a :class:`DirUsage` for every directory, children before their parent.

    The root comes last. Results stream while the walk goes on; memory holds the
    walk stack and the identities of directories and hard-linked files seen.
    Arguments are checked at the call, the tree is read as the iterator is
    consumed. Options mean what they mean in :func:`scan`.
    A regular-file root yields one synthetic ``DirUsage`` with its bytes,
    ``files=1``, ``dirs=0`` and ``depth=0``.

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = pathlib.Path(tmp, "sub").mkdir()
    ...     _ = pathlib.Path(tmp, "sub", "a.txt").write_bytes(b"hello")
    ...     found = [(d.depth, d.apparent_bytes, d.files) for d in iter_dirs(tmp)]
    >>> found
    [(1, 5, 1), (0, 5, 1)]
    """
    name, handle = check_path(path), as_handler(on_error)
    options = WalkOptions(follow_symlinks, one_filesystem, count_links, include_dirs)
    return _only_dirs(walk(name, options, handle))


def _only_dirs(
    items: Generator[FileUsage | DirUsage, None, None],
) -> Generator[DirUsage, None, None]:
    with closing(items):  # closing this generator closes the walk and its listings at once
        for item in items:
            if isinstance(item, DirUsage):
                yield item


def dir_size(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the total apparent size (``st_size``) in bytes of every file under ``path``.

    Hard-linked files count once. Symlinked directories and Windows junctions are
    not entered unless ``follow_symlinks``; loops are skipped silently either way.
    ``on_error`` is ``"raise"`` (the default here), ``"ignore"`` or a callable that
    receives each :class:`OSError`.

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = pathlib.Path(tmp, "a.txt").write_bytes(b"hello")
    ...     _ = pathlib.Path(tmp, "b.txt").write_bytes(b"world!")
    ...     dir_size(tmp)
    11
    """
    name, handle = check_path(path), as_handler(on_error)
    options = WalkOptions(follow_symlinks=follow_symlinks, report_cycles=False)
    items = walk(name, options, handle)
    return sum(item.apparent_bytes for item in items if isinstance(item, FileUsage))


def file_count(
    path: PathLike,
    *,
    follow_symlinks: bool = False,
    on_error: OnError = "raise",
) -> int:
    """Return the number of files under ``path``, one per directory entry.

    Every name of a hard-linked file counts, and so does every link left
    unfollowed. Options mean what they mean in :func:`dir_size`.

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = pathlib.Path(tmp, "sub").mkdir()
    ...     _ = pathlib.Path(tmp, "sub", "a.txt").write_bytes(b"hello")
    ...     _ = pathlib.Path(tmp, "b.txt").write_bytes(b"world!")
    ...     file_count(tmp)
    2
    """
    name, handle = check_path(path), as_handler(on_error)
    options = WalkOptions(follow_symlinks=follow_symlinks, report_cycles=False)
    return sum(1 for item in walk(name, options, handle) if isinstance(item, FileUsage))
