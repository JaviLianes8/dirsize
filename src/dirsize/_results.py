"""The typed results: one entry, one directory's subtree, one measured path."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._errors import ScanError
from ._types import Measure, check_measure


@dataclass(frozen=True)
class FileUsage:
    """Size of one non-directory entry: a file, a link that was not followed, a device.

    ``is_link`` is true for a symlink or a Windows junction that was not entered.

    >>> item = FileUsage("notes.txt", apparent_bytes=5, disk_bytes=4096)
    >>> item.size(), item.size("apparent"), item.is_link
    (4096, 5, False)
    """

    path: str
    apparent_bytes: int
    disk_bytes: int
    is_link: bool = False

    def size(self, by: Measure = "disk") -> int:
        """Return ``disk_bytes`` or ``apparent_bytes``; any other ``by`` is a ``ValueError``.

        >>> FileUsage("a", 5, 4096).size("apparent")
        5
        """
        return self.disk_bytes if check_measure(by) == "disk" else self.apparent_bytes


@dataclass(frozen=True)
class DirUsage:
    """Totals for one directory and everything below it.

    ``files`` counts every non-directory entry, one per name; a file with several
    hard links adds its bytes once unless ``count_links`` was set. ``links`` is the
    number of those entries that are links left unfollowed. ``dirs`` counts the
    directories entered below this one, ``errors`` the errors met inside it (a
    count; :attr:`Usage.errors` holds the errors themselves). ``depth`` is 0 for
    the root, 1 for its subdirectories, and so on.
    A regular-file root is represented by a synthetic total with ``files=1``,
    ``dirs=0`` and ``depth=0``.

    >>> folder = DirUsage("src", 1200, 8192, files=3, dirs=1, links=0, errors=0, depth=1)
    >>> folder.size(), folder.size("apparent")
    (8192, 1200)
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
        """Return ``disk_bytes`` or ``apparent_bytes``; any other ``by`` is a ``ValueError``.

        >>> DirUsage("src", 1200, 8192, 3, 1, 0, 0, 1).size("apparent")
        1200
        """
        return self.disk_bytes if check_measure(by) == "disk" else self.apparent_bytes


@dataclass(frozen=True)
class Usage:
    """Result of :func:`dirsize.scan`: the totals for one path plus every error met.

    ``measured`` is false when root metadata or its directory listing could not
    be opened; the totals are then 0. Errors after opening the listing retain
    partial totals and ``measured=True``. ``ok`` is true when nothing went wrong.

    >>> usage = Usage("project", apparent_bytes=5, disk_bytes=4096, files=1, dirs=0, links=0)
    >>> usage.ok, usage.measured, usage.size("apparent")
    (True, True, 5)
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
        """True when the whole tree was measured without a single error.

        >>> Usage("gone", 0, 0, 0, 0, 0, measured=False).ok
        False
        """
        return self.measured and not self.errors

    def size(self, by: Measure = "disk") -> int:
        """Return ``disk_bytes`` or ``apparent_bytes``; any other ``by`` is a ``ValueError``.

        >>> Usage("project", 5, 4096, 1, 0, 0).size()
        4096
        """
        return self.disk_bytes if check_measure(by) == "disk" else self.apparent_bytes
