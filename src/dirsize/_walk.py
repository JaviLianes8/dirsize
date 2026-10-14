"""One iterative post-order walk shared by every public function."""

from __future__ import annotations

import os
import stat
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from typing import Protocol

from ._platform import disk_bytes, is_link
from ._types import DirUsage, ErrorHandler, FileUsage, cycle_error

Key = tuple[int, int]
Item = FileUsage | DirUsage


class _Entries(Iterator[os.DirEntry[str]], Protocol):
    def close(self) -> None: ...


@dataclass(frozen=True)
class WalkOptions:
    follow_symlinks: bool = False
    one_filesystem: bool = False
    count_links: bool = False
    include_dirs: bool = False
    report_cycles: bool = True


@dataclass
class _Frame:
    path: str
    key: Key
    depth: int
    entries: Iterator[os.DirEntry[str]]
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


@dataclass
class _State:
    options: WalkOptions
    handle: ErrorHandler
    root_dev: int = 0
    seen_files: set[Key] = field(default_factory=set)
    seen_dirs: set[Key] = field(default_factory=set)
    ancestors: set[Key] = field(default_factory=set)

    def fail(self, error: OSError) -> int:
        self.handle(error)
        return 1

    def file_bytes(self, path: str, info: os.stat_result) -> tuple[int, int]:
        key = (info.st_dev, info.st_ino)
        if not self.options.count_links and info.st_nlink > 1 and info.st_ino != 0:
            if key in self.seen_files:
                return 0, 0
            self.seen_files.add(key)
        return info.st_size, disk_bytes(path, info)

    def own_bytes(self, path: str, info: os.stat_result) -> tuple[int, int]:
        if not self.options.include_dirs:
            return 0, 0
        return info.st_size, disk_bytes(path, info)


def _lookup(path: str, follow: bool, state: _State) -> tuple[os.stat_result, bool] | None:
    """Return the entry's stat and whether it is an unfollowed link, or None on error."""
    try:
        info = os.stat(path, follow_symlinks=False)
        linked = is_link(info)
        if linked and follow:
            info = os.stat(path)
            linked = False
    except OSError as error:
        state.fail(error)
        return None
    return info, linked


def walk(root: str, options: WalkOptions, handle: ErrorHandler) -> Iterator[Item]:
    """Yield a :class:`FileUsage` per non-directory and a :class:`DirUsage` per directory.

    Directories come after their contents, so the last item is the root's total.
    Nothing is yielded when the root itself cannot be read.
    """
    state = _State(options, handle)
    found = _lookup(root, True, state)
    if found is None:
        return
    info, _ = found
    state.root_dev = info.st_dev
    if not stat.S_ISDIR(info.st_mode):
        apparent, disk = state.file_bytes(root, info)
        yield FileUsage(root, apparent, disk)
        yield DirUsage(root, apparent, disk, 1, 0, 0, 0, 0)
        return
    root_frame = _open(root, info, 0, state)
    if root_frame is None:
        return
    stack = [root_frame]
    while stack:
        frame = stack[-1]
        try:
            entry = next(frame.entries, None)
        except OSError as error:
            frame.errors += state.fail(error)
            entry = None
        if entry is None:
            stack.pop()
            state.ancestors.discard(frame.key)
            done = DirUsage(
                frame.path,
                frame.apparent,
                frame.disk,
                frame.files,
                frame.dirs,
                frame.links,
                frame.errors,
                frame.depth,
            )
            if stack:
                stack[-1].add(done)
            yield done
            continue
        child = yield from _visit(entry.path, frame, state)
        if child is not None:
            stack.append(child)


def _open(path: str, info: os.stat_result, depth: int, state: _State) -> _Frame | None:
    try:
        entries = os.scandir(path)
    except OSError as error:
        state.fail(error)
        return None
    key = (info.st_dev, info.st_ino)
    if info.st_ino != 0:
        state.seen_dirs.add(key)
        state.ancestors.add(key)
    frame = _Frame(path, key, depth, _closing(entries))
    frame.apparent, frame.disk = state.own_bytes(path, info)
    return frame


def _closing(entries: _Entries) -> Iterator[os.DirEntry[str]]:
    try:
        yield from entries
    finally:
        entries.close()


def _visit(path: str, frame: _Frame, state: _State) -> Generator[Item, None, _Frame | None]:
    found = _lookup(path, state.options.follow_symlinks, state)
    if found is None:
        frame.errors += 1
        return None
    info, linked = found
    if stat.S_ISDIR(info.st_mode) and not linked:
        if state.options.one_filesystem and info.st_dev != state.root_dev:
            return None
        key = (info.st_dev, info.st_ino)
        if info.st_ino != 0 and key in state.ancestors:
            if state.options.report_cycles:
                frame.errors += state.fail(cycle_error(path))
            return None
        if info.st_ino != 0 and key in state.seen_dirs:
            return None
        child = _open(path, info, frame.depth + 1, state)
        if child is None:
            frame.errors += 1
        return child
    apparent, disk = state.file_bytes(path, info)
    frame.apparent += apparent
    frame.disk += disk
    frame.files += 1
    frame.links += int(linked)
    yield FileUsage(path, apparent, disk, linked)
    return None
