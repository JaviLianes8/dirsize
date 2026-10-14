"""One iterative post-order walk shared by every public function."""

from __future__ import annotations

import os
import stat
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from typing import Protocol

from ._platform import apparent_bytes, disk_bytes, is_link
from ._types import DirUsage, ErrorHandler, FileUsage, WalkOptions, cycle_error

Key = tuple[int, int]
Item = FileUsage | DirUsage


class _Entries(Iterator[os.DirEntry[str]], Protocol):
    def close(self) -> None: ...


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

    def result(self) -> DirUsage:
        totals = (self.apparent, self.disk, self.files, self.dirs, self.links, self.errors)
        return DirUsage(self.path, *totals, self.depth)


@dataclass
class Seen:
    """Files and directories already counted; shared across roots, like du's arguments."""

    files: set[Key] = field(default_factory=set)
    dirs: set[Key] = field(default_factory=set)


@dataclass
class _State:
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
        shared = info.st_nlink > 1 or self.options.follow_symlinks
        if not self.options.count_links and shared and info.st_ino != 0:
            if key in self.seen.files:
                return 0, 0
            self.seen.files.add(key)
        return apparent_bytes(info), disk_bytes(path, info)

    def own_bytes(self, path: str, info: os.stat_result) -> tuple[int, int]:
        if not self.options.include_dirs:
            return 0, 0
        return apparent_bytes(info), disk_bytes(path, info)


def _lookup(path: str, follow: bool, state: _State) -> tuple[os.stat_result, bool] | None:
    """Return the entry's stat and whether it is an unfollowed link, or None on error."""
    try:
        info = os.stat(path, follow_symlinks=False)
        linked = is_link(info)
        if linked and follow:  # a dangling link is an error here, as in du -L
            info, linked = os.stat(path), False
    except OSError as error:
        state.fail(error)
        return None
    return info, linked


def walk(
    root: str, options: WalkOptions, handle: ErrorHandler, seen: Seen | None = None
) -> Iterator[Item]:
    """Yield a :class:`FileUsage` per non-directory and a :class:`DirUsage` per directory.

    Directories come after their contents, so the last item is the root's total.
    Nothing is yielded when the root cannot be found, or was counted already in ``seen``.
    """
    state = _State(options, handle, seen or Seen())
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
    if info.st_ino != 0 and (info.st_dev, info.st_ino) in state.seen.dirs:
        return
    root_frame = _open(root, info, 0, state)
    if root_frame is None:
        apparent, disk = state.own_bytes(root, info)
        yield DirUsage(root, apparent, disk, 0, 0, 0, 1, 0)
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
            done = frame.result()
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
        state.seen.dirs.add(key)
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
            # Like du, only a physical walk warns; a followed loop is just not re-entered.
            if state.options.report_cycles and not state.options.follow_symlinks:
                frame.errors += state.fail(cycle_error(path))
            return None
        if info.st_ino != 0 and key in state.seen.dirs:
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
