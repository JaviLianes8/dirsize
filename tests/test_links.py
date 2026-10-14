from __future__ import annotations

import os
from pathlib import Path

from helpers import junction, symlink, write

from dirsize import dir_size, file_count, iter_dirs, scan


def _real(root: Path) -> Path:
    write(root / "real" / "file.bin", b"d" * 50)
    return root / "real"


def test_symlinked_directory_is_a_link_not_a_subtree(tmp_path: Path) -> None:
    symlink(tmp_path / "link", _real(tmp_path))
    usage = scan(tmp_path)
    assert usage.files == 2 and usage.links == 1 and usage.dirs == 1
    assert usage.apparent_bytes == 50 + os.lstat(tmp_path / "link").st_size


def test_follow_symlinks_enters_the_target_once(tmp_path: Path) -> None:
    real = _real(tmp_path)
    write(tmp_path / "other" / "x.bin", b"x" * 7)
    symlink(tmp_path / "other" / "link", real)
    usage = scan(tmp_path / "other", follow_symlinks=True)
    assert (usage.apparent_bytes, usage.files, usage.links) == (57, 2, 0)


def test_junction_is_not_entered_by_default(tmp_path: Path) -> None:
    junction(tmp_path / "jn", _real(tmp_path))
    usage = scan(tmp_path)
    assert usage.links == 1 and usage.dirs == 1
    assert dir_size(tmp_path) == 50 + os.lstat(tmp_path / "jn").st_size
    assert file_count(tmp_path) == 2


def test_junction_to_an_ancestor_does_not_recurse(tmp_path: Path) -> None:
    write(tmp_path / "inner" / "f.bin", b"f" * 30)
    junction(tmp_path / "inner" / "loop", tmp_path)
    assert scan(tmp_path).apparent_bytes == 30
    assert [Path(d.path).name for d in iter_dirs(tmp_path)] == ["inner", tmp_path.name]


def test_followed_junction_loop_is_reported_as_a_cycle(tmp_path: Path) -> None:
    write(tmp_path / "inner" / "f.bin", b"f" * 30)
    junction(tmp_path / "inner" / "loop", tmp_path)
    usage = scan(tmp_path, follow_symlinks=True)
    assert usage.apparent_bytes == 30
    assert [e.kind for e in usage.errors] == ["cycle"]
    assert usage.errors[0].path == os.fspath(tmp_path / "inner" / "loop")


def test_followed_symlink_loop_is_reported_as_a_cycle(tmp_path: Path) -> None:
    write(tmp_path / "inner" / "f.bin", b"f" * 30)
    symlink(tmp_path / "inner" / "loop", tmp_path)
    usage = scan(tmp_path, follow_symlinks=True)
    assert usage.apparent_bytes == 30
    assert [e.kind for e in usage.errors] == ["cycle"]


def test_dir_size_keeps_skipping_loops_silently(tmp_path: Path) -> None:
    write(tmp_path / "inner" / "f.bin", b"f" * 30)
    symlink(tmp_path / "inner" / "loop", tmp_path)
    assert dir_size(tmp_path, follow_symlinks=True) == 30


def test_two_links_to_one_directory_count_it_once(tmp_path: Path) -> None:
    real = _real(tmp_path / "data")
    write(tmp_path / "view" / "keep.bin", b"k")
    symlink(tmp_path / "view" / "a", real)
    symlink(tmp_path / "view" / "b", real)
    usage = scan(tmp_path / "view", follow_symlinks=True)
    assert (usage.apparent_bytes, usage.files, usage.dirs) == (51, 2, 1)
    assert usage.ok


def test_symlinked_root_is_resolved(tmp_path: Path) -> None:
    root = symlink(tmp_path / "root", _real(tmp_path))
    assert scan(root).apparent_bytes == 50


def test_broken_symlink_counts_as_a_link_without_following(tmp_path: Path) -> None:
    symlink(tmp_path / "dangling", tmp_path / "missing")
    usage = scan(tmp_path)
    assert usage.files == 1 and usage.links == 1 and usage.ok


def test_broken_symlink_is_an_error_when_following(tmp_path: Path) -> None:
    symlink(tmp_path / "dangling", tmp_path / "missing")
    usage = scan(tmp_path, follow_symlinks=True)
    assert [e.kind for e in usage.errors] == ["missing"] and usage.files == 0
    (root,) = iter_dirs(tmp_path, follow_symlinks=True)
    assert root.errors == 1


def test_two_followed_links_to_one_file_count_it_once(tmp_path: Path) -> None:
    target = write(tmp_path / "data" / "f.bin", b"f" * 40)
    symlink(tmp_path / "view" / "a", target)
    symlink(tmp_path / "view" / "b", target)
    usage = scan(tmp_path / "view", follow_symlinks=True)
    assert (usage.apparent_bytes, usage.files) == (40, 2)
    assert scan(tmp_path / "view", follow_symlinks=True, count_links=True).apparent_bytes == 80
