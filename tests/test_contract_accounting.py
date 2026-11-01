"""Accounting switches and public error types on controlled filesystem metadata."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest

import dirsize as d
from dirsize import _state


@pytest.mark.parametrize("count_links", [False, True])
def test_iter_dirs_counts_hardlinks_in_child_and_root(tmp_path: Path, count_links: bool) -> None:
    child = tmp_path / "child"
    child.mkdir()
    file = child / "first"
    file.write_bytes(b"abc")
    os.link(file, child / "second")
    one = d.scan(file)
    found = list(d.iter_dirs(tmp_path, count_links=count_links))
    assert [entry.path for entry in found] == [str(child), str(tmp_path)]
    for entry in found:
        assert entry.apparent_bytes == (6 if count_links else 3)
        assert entry.disk_bytes == one.disk_bytes * (2 if count_links else 1)
        assert entry.files == 2


@pytest.mark.parametrize("include_dirs", [False, True])
def test_directory_allocation_includes_root_and_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_dirs: bool
) -> None:
    # Nonzero synthetic allocation makes the switch observable on every platform.
    (tmp_path / "child").mkdir()
    monkeypatch.setattr(_state, "disk_bytes", lambda path, info: 4096)
    total = 8192 if include_dirs else 0
    assert d.scan(tmp_path, include_dirs=include_dirs).disk_bytes == total
    child, root = d.iter_dirs(tmp_path, include_dirs=include_dirs)
    assert child.disk_bytes == total // 2 and root.disk_bytes == total
    assert root.dirs == 1 and root.apparent_bytes == 0


@pytest.mark.parametrize("kind", ["file", "dir"])
def test_largest_honours_foreign_device_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: Literal["file", "dir"]
) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    payload = foreign / "data"
    payload.write_bytes(b"abc")
    original = os.stat

    def metadata(path: str, *, follow_symlinks: bool = True) -> os.stat_result:
        info = original(path, follow_symlinks=follow_symlinks)
        if os.fspath(path) == str(foreign):
            fields = list(info)
            fields[2] += 1
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(os, "stat", metadata)
    limited = d.largest(tmp_path, kind=kind, one_filesystem=True)
    full = d.largest(tmp_path, kind=kind)
    assert {entry.path for entry in full} == (
        {str(payload)} if kind == "file" else {str(foreign), str(tmp_path)}
    )
    assert {entry.path for entry in limited} == (set() if kind == "file" else {str(tmp_path)})
    assert all(entry.apparent_bytes == 0 for entry in limited)


def test_on_error_alias_and_typed_callback_consumer(tmp_path: Path) -> None:
    assert d.OnError == Literal["raise", "ignore"] | Callable[[OSError], None]
    errors: list[OSError] = []
    policy: d.OnError = errors.append
    missing = tmp_path / "missing"
    d.scan(missing, on_error=policy)
    list(d.iter_dirs(missing, on_error=policy))
    d.largest(missing, on_error=policy)
    d.dir_size(missing, on_error=policy)
    d.file_count(missing, on_error=policy)
    assert len(errors) == 5 and all(isinstance(e, FileNotFoundError) for e in errors)


def test_windows_loop_code_is_a_cycle() -> None:
    error = OSError(22, "loop", "p")
    error.winerror = 1921
    assert d.ScanError.from_os_error(error) == d.ScanError("p", "cycle", "loop")


def test_bare_error_message_is_preserved() -> None:
    assert d.ScanError.from_os_error(OSError("bare")) == d.ScanError("", "other", "bare")
    assert d.ScanError.from_os_error(OSError(22, "message", "p")) == d.ScanError(
        "p", "other", "message"
    )
