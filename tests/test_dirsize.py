from __future__ import annotations

import os
from pathlib import Path

import pytest

from dirsize import dir_size, file_count


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def test_sums_nested_file_sizes(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", b"x" * 10)
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(sub / "b.bin", b"y" * 25)
    deep = sub / "deep"
    deep.mkdir()
    _write(deep / "c.bin", b"z" * 5)
    assert dir_size(tmp_path) == 40


def test_empty_directory_is_zero(tmp_path: Path) -> None:
    assert dir_size(tmp_path) == 0
    assert file_count(tmp_path) == 0


def test_file_count_counts_every_file(tmp_path: Path) -> None:
    _write(tmp_path / "a", b"1")
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(sub / "b", b"2")
    _write(sub / "c", b"3")
    assert file_count(tmp_path) == 3


def test_accepts_string_path(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", b"abcd")
    assert dir_size(str(tmp_path)) == 4


def test_on_error_raise_propagates_for_missing_path(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        dir_size(tmp_path / "does-not-exist")


def test_on_error_ignore_returns_zero_for_missing_path(tmp_path: Path) -> None:
    assert dir_size(tmp_path / "does-not-exist", on_error="ignore") == 0


def test_on_error_callback_receives_the_error(tmp_path: Path) -> None:
    errors: list[OSError] = []
    result = dir_size(tmp_path / "missing", on_error=errors.append)
    assert result == 0
    assert len(errors) == 1
    assert isinstance(errors[0], OSError)


def test_rejects_unknown_on_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        dir_size(tmp_path, on_error="skip")  # type: ignore[arg-type]


def test_hardlinks_are_counted_once(tmp_path: Path) -> None:
    original = tmp_path / "original.bin"
    _write(original, b"q" * 100)
    link = tmp_path / "linked.bin"
    try:
        os.link(original, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("this filesystem cannot create hardlinks")
    if link.stat().st_nlink <= 1 or link.stat().st_ino == 0:
        pytest.skip("this filesystem does not report hardlink metadata")
    assert dir_size(tmp_path) == 100


def test_symlinked_directory_is_not_descended_by_default(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    _write(real / "file.bin", b"d" * 50)
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("this filesystem cannot create symlinks")
    # The link itself counts with its own size, like du; its target is not entered.
    assert dir_size(tmp_path) == 50 + os.lstat(link).st_size


def test_follow_symlinks_survives_a_loop(tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    _write(inner / "file.bin", b"d" * 30)
    loop = inner / "loop"
    try:
        os.symlink(tmp_path, loop, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("this filesystem cannot create symlinks")
    assert dir_size(tmp_path, follow_symlinks=True) == 30
