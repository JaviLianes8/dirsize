"""One iterative post-order walk shared by every public function."""

from __future__ import annotations

import os
import stat
from collections.abc import Generator, Iterator
from typing import Protocol

from ._errors import cycle_error
from ._platform import is_link
from ._results import DirUsage, FileUsage
from ._state import Frame, Seen, State
from ._types import ErrorHandler, WalkOptions

Item = FileUsage | DirUsage


class _Entries(Iterator[os.DirEntry[str]], Protocol):
    def close(self) -> None: ...


def _lookup(path: str, follow: bool, state: State) -> tuple[os.stat_result, bool] | None:
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
) -> Generator[Item, None, None]:
    """Yield a :class:`FileUsage` per non-directory and a :class:`DirUsage` per directory.

    Directories come after their contents, so the last item is the root's total.
    Nothing is yielded when the root cannot be found, or was counted already in ``seen``.
    """
    state = State(options, handle, seen or Seen())
    found = _lookup(root, True, state)
    if found is None:
        return
    info, _ = found
    state.root_dev = info.st_dev
    if not stat.S_ISDIR(info.st_mode):
        key = (info.st_dev, info.st_ino)
        if not options.count_links and info.st_ino != 0 and key in state.seen.files:
            return
        apparent, disk = state.file_bytes(root, info)
        if info.st_ino != 0:
            state.seen.files.add(key)
        yield FileUsage(root, apparent, disk)
        yield DirUsage(root, apparent, disk, 1, 0, 0, 0, 0)
        return
    if info.st_ino != 0 and (info.st_dev, info.st_ino) in state.seen.dirs:
        return
    root_frame = _open(root, info, 0, state)
    if root_frame is None:
        yield state.unreadable(root, info, 0)
        return
    stack = [root_frame]
    try:
        while stack:
            frame = stack[-1]
            try:
                entry = next(frame.entries, None)
            except OSError as error:
                frame.errors += state.fail(error)
                entry = None
            if entry is None:
                stack.pop().entries.close()
                state.ancestors.discard(frame.key)
                done = frame.result()
                if stack:
                    stack[-1].add(done)
                yield done
                continue
            child = yield from _visit(entry.path, frame, state)
            if child is not None:
                stack.append(child)
    finally:  # an early stop, an error or a closed generator: release every listing now
        for frame in stack:
            frame.entries.close()


def _open(path: str, info: os.stat_result, depth: int, state: State) -> Frame | None:
    try:
        entries = os.scandir(path)
    except OSError as error:
        state.fail(error)
        return None
    key = (info.st_dev, info.st_ino)
    if info.st_ino != 0:
        state.seen.dirs.add(key)
        state.ancestors.add(key)
    frame = Frame(path, key, depth, _closing(entries))
    frame.apparent, frame.disk = state.own_bytes(path, info)
    return frame


def _closing(entries: _Entries) -> Generator[os.DirEntry[str], None, None]:
    try:
        yield from entries
    finally:
        entries.close()


def _visit(path: str, frame: Frame, state: State) -> Generator[Item, None, Frame | None]:
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
            failed = state.unreadable(path, info, frame.depth + 1)
            frame.add(failed)
            yield failed
        return child
    apparent, disk = state.file_bytes(path, info)
    frame.apparent += apparent
    frame.disk += disk
    frame.files += 1
    frame.links += int(linked)
    yield FileUsage(path, apparent, disk, linked)
    return None
