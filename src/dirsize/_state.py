"""The walk's bookkeeping: open directories, identities already counted, the options."""

from __future__ import annotations

import os
from collections.abc import Generator
from dataclasses import dataclass, field

from ._platform import apparent_bytes, disk_bytes
from ._results import DirUsage
from ._types import ErrorHandler, WalkOptions

Key = tuple[int, int]


@dataclass
class Frame:
    """One directory being listed, with the totals of what was met inside so far."""

    path: str
    key: Key
    depth: int
    entries: Generator[os.DirEntry[str], None, None]
    apparent: int = 0
    disk: int = 0
    files: int = 0
    dirs: int = 0
    links: int = 0
    errors: int = 0

    def add(self, child: DirUsage) -> None:
        self.apparent += child.apparent_bytes
        self.disk += child.disk_bytes
        self.files += child.files
        self.dirs += child.dirs + 1
        self.links += child.links
        self.errors += child.errors

    def result(self) -> DirUsage:
        totals = (self.apparent, self.disk, self.files, self.dirs, self.links, self.errors)
        return DirUsage(self.path, *totals, self.depth)


@dataclass
class Seen:
    """Files and directories already counted; shared across roots, like du's arguments."""

    files: set[Key] = field(default_factory=set)
    dirs: set[Key] = field(default_factory=set)
    track_all: bool = False


@dataclass
class RootStatus:
    """Whether the root's metadata and directory listing could be opened."""

    measured: bool = False


@dataclass
class State:
    """Everything one walk shares: options, error policy, identities and ancestors."""

    options: WalkOptions
    handle: ErrorHandler
    seen: Seen
    root_dev: int = 0
    ancestors: set[Key] = field(default_factory=set)

    def fail(self, error: OSError) -> int:
        self.handle(error)
        return 1

    def file_bytes(self, path: str, info: os.stat_result) -> tuple[int, int]:
        key = (info.st_dev, info.st_ino)
        # Following links can reach one file by several paths even without hard links.
        shared = info.st_nlink > 1 or self.options.follow_symlinks or self.seen.track_all
        if not self.options.count_links and shared and info.st_ino != 0:
            if key in self.seen.files:
                return 0, 0
            self.seen.files.add(key)
        return apparent_bytes(info), disk_bytes(path, info)

    def own_bytes(self, path: str, info: os.stat_result) -> tuple[int, int]:
        if not self.options.include_dirs:
            return 0, 0
        return apparent_bytes(info), disk_bytes(path, info)

    def unreadable(self, path: str, info: os.stat_result, depth: int) -> DirUsage:
        """A directory that could not be listed: its own size, as du counts it, and one error."""
        apparent, disk = self.own_bytes(path, info)
        return DirUsage(path, apparent, disk, 0, 0, 0, 1, depth)
