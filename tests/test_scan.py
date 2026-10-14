from __future__ import annotations

import os
from pathlib import Path

import pytest
from helpers import hardlink, write

import dirsize._walk as walk_module
from dirsize import Usage, iter_dirs, scan


def _tree(root: Path) -> None:
    write(root / "a.bin", b"a" * 10)
    write(root / "sub" / "b.bin", b"b" * 25)
    write(root / "sub" / "deep" / "c.bin", b"c" * 5)


def test_scan_totals_files_dirs_and_bytes(tmp_path: Path) -> None:
    _tree(tmp_path)
    usage = scan(tmp_path)
    assert isinstance(usage, Usage)
    assert (usage.apparent_bytes, usage.files, usage.dirs, usage.links) == (40, 3, 2, 0)
    assert usage.path == os.fspath(tmp_path)
    assert usage.ok and usage.measured and usage.errors == ()


def test_disk_bytes_cover_every_file(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert scan(tmp_path).disk_bytes >= 40


def test_empty_directory_measures_zero(tmp_path: Path) -> None:
    usage = scan(tmp_path)
    assert (usage.apparent_bytes, usage.disk_bytes, usage.files, usage.dirs) == (0, 0, 0, 0)
    assert usage.measured


def test_a_file_root_is_measured_on_its_own(tmp_path: Path) -> None:
    target = write(tmp_path / "one.bin", b"x" * 7)
    usage = scan(target)
    assert (usage.apparent_bytes, usage.files, usage.dirs) == (7, 1, 0)


def test_hard_links_count_once_but_every_name_is_a_file(tmp_path: Path) -> None:
    original = write(tmp_path / "a" / "original.bin", b"q" * 100)
    hardlink(tmp_path / "linked.bin", original)
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 100
    assert usage.files == 2


def test_count_links_counts_every_hard_link(tmp_path: Path) -> None:
    original = write(tmp_path / "original.bin", b"q" * 100)
    hardlink(tmp_path / "linked.bin", original)
    usage = scan(tmp_path, count_links=True)
    assert usage.apparent_bytes == 200
    assert usage.disk_bytes == 2 * scan(original).disk_bytes


def test_hard_link_bytes_land_in_one_directory_only(tmp_path: Path) -> None:
    original = write(tmp_path / "one" / "f.bin", b"q" * 64)
    (tmp_path / "two").mkdir()
    hardlink(tmp_path / "two" / "g.bin", original)
    sizes = {Path(d.path).name: d.apparent_bytes for d in iter_dirs(tmp_path)}
    assert sizes["one"] + sizes["two"] == 64
    assert sizes[tmp_path.name] == 64


def test_include_dirs_adds_each_directory_entry(tmp_path: Path) -> None:
    _tree(tmp_path)
    expected = sum(
        os.stat(p).st_size for p in (tmp_path, tmp_path / "sub", tmp_path / "sub" / "deep")
    )
    assert scan(tmp_path, include_dirs=True).apparent_bytes == 40 + expected


def test_one_filesystem_skips_directories_on_another_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree(tmp_path)
    mounted = os.fspath(tmp_path / "sub")
    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = True) -> os.stat_result:
        info = real_stat(path, follow_symlinks=follow_symlinks)
        if os.fspath(path) == mounted:
            fields = list(info)
            fields[2] = info.st_dev + 1
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(walk_module.os, "stat", fake_stat)
    assert scan(tmp_path, one_filesystem=True).apparent_bytes == 10
    assert scan(tmp_path).apparent_bytes == 40


def test_unknown_on_error_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="on_error"):
        scan(tmp_path, on_error="skip")  # type: ignore[arg-type]
