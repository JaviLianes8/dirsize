from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from helpers import unreadable, write

from dirsize import ScanError, dir_size, iter_dirs, scan


def _locked_tree(root: Path) -> Path:
    write(root / "open" / "a.bin", b"a" * 11)
    locked = root / "locked"
    write(locked / "secret.bin", b"s" * 99)
    return locked


def test_permission_error_is_reported_and_the_rest_is_measured(tmp_path: Path) -> None:
    locked = _locked_tree(tmp_path)
    with unreadable(locked):
        usage = scan(tmp_path)
    assert usage.apparent_bytes == 11
    assert not usage.ok
    (error,) = usage.errors
    assert error.kind == "permission" and error.path == os.fspath(locked)
    assert error.message


def test_errors_are_counted_on_the_directory_that_holds_them(tmp_path: Path) -> None:
    locked = _locked_tree(tmp_path)
    with unreadable(locked):
        totals = {Path(d.path).name: d.errors for d in iter_dirs(tmp_path)}
    assert totals == {"open": 0, tmp_path.name: 1}


def test_raise_stops_at_the_first_error(tmp_path: Path) -> None:
    locked = _locked_tree(tmp_path)
    with unreadable(locked), pytest.raises(PermissionError):
        scan(tmp_path, on_error="raise")


def test_callback_sees_each_os_error(tmp_path: Path) -> None:
    locked = _locked_tree(tmp_path)
    seen: list[OSError] = []
    with unreadable(locked):
        usage = scan(tmp_path, on_error=seen.append)
    assert len(seen) == 1 and isinstance(seen[0], PermissionError)
    assert len(usage.errors) == 1


def test_dir_size_defaults_to_raising(tmp_path: Path) -> None:
    locked = _locked_tree(tmp_path)
    with unreadable(locked), pytest.raises(PermissionError):
        dir_size(tmp_path)


def test_missing_root_is_not_measured(tmp_path: Path) -> None:
    usage = scan(tmp_path / "nope")
    assert not usage.measured and not usage.ok
    assert (usage.apparent_bytes, usage.files) == (0, 0)
    assert usage.errors[0].kind == "missing"


def test_error_kinds_are_classified() -> None:
    assert ScanError.from_os_error(PermissionError(errno.EACCES, "x", "p")).kind == "permission"
    assert ScanError.from_os_error(FileNotFoundError(errno.ENOENT, "x", "p")).kind == "missing"
    assert ScanError.from_os_error(NotADirectoryError(errno.ENOTDIR, "x", "p")).kind == "missing"
    assert ScanError.from_os_error(OSError(errno.ELOOP, "x", "p")).kind == "cycle"
    assert ScanError.from_os_error(OSError(errno.EIO, "x", "p")).kind == "other"


def test_error_keeps_path_and_message() -> None:
    error = ScanError.from_os_error(OSError(errno.EIO, "disk trouble", b"raw"))
    assert (error.path, error.message) == ("raw", "disk trouble")
    assert ScanError.from_os_error(OSError("bare")).path == ""


def test_scandir_failure_is_reported_on_any_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = _locked_tree(tmp_path)
    real_scandir = os.scandir

    def guarded(path: str) -> object:
        if os.fspath(path) == os.fspath(locked):
            raise PermissionError(errno.EACCES, "denied", os.fspath(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded)
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 11 and usage.dirs == 1
    assert [(e.kind, e.path) for e in usage.errors] == [("permission", os.fspath(locked))]
    with pytest.raises(PermissionError):
        dir_size(tmp_path)


def test_error_while_listing_ends_that_directory_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path / "keep.bin", b"k" * 5)
    write(tmp_path / "bad" / "x.bin", b"x" * 9)
    bad = os.fspath(tmp_path / "bad")
    real_scandir = os.scandir

    class Failing:
        def __iter__(self) -> Failing:
            return self

        def __next__(self) -> os.DirEntry[str]:
            raise OSError(errno.EIO, "read failed", bad)

        def close(self) -> None:
            return None

    def flaky(path: str) -> object:
        return Failing() if os.fspath(path) == bad else real_scandir(path)

    monkeypatch.setattr(os, "scandir", flaky)
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 5 and usage.dirs == 1
    assert [e.kind for e in usage.errors] == ["other"]


def test_nested_errors_add_up_to_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path / "a" / "b" / "locked" / "x.bin", b"x")
    write(tmp_path / "a" / "keep.bin", b"k")
    locked = os.fspath(tmp_path / "a" / "b" / "locked")
    real_scandir = os.scandir

    def guarded(path: str) -> object:
        if os.fspath(path) == locked:
            raise PermissionError(errno.EACCES, "denied", locked)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded)
    errors = {Path(d.path).name: d.errors for d in iter_dirs(tmp_path)}
    assert errors == {"b": 1, "a": 1, tmp_path.name: 1}


def test_unreadable_root_reports_its_own_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = os.fspath(tmp_path)
    real_scandir = os.scandir

    def guarded(path: str) -> object:
        if os.fspath(path) == root:
            raise PermissionError(errno.EACCES, "denied", root)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded)
    (only,) = iter_dirs(tmp_path)
    assert (only.path, only.errors, only.files, only.depth) == (root, 1, 0, 0)
    usage = scan(tmp_path)
    assert usage.measured and [e.kind for e in usage.errors] == ["permission"]
