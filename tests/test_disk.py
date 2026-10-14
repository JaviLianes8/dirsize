from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from helpers import write

from dirsize import scan
from dirsize._platform import apparent_bytes, is_link, posix_disk_bytes

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="NTFS allocation")


def _stat(size: int, **extra: int) -> os.stat_result:
    # Duck-typed so POSIX-only fields can be faked on Windows and the other way round.
    return cast(os.stat_result, SimpleNamespace(st_mode=0o100644, st_size=size, **extra))


def _run(*cmd: str) -> None:
    done = subprocess.run(cmd, capture_output=True, check=False)
    if done.returncode != 0:
        pytest.skip(f"{cmd[0]} is not available here")


def test_posix_disk_bytes_are_512_byte_blocks() -> None:
    assert posix_disk_bytes("f", _stat(10, st_blocks=8)) == 4096
    assert posix_disk_bytes("f", _stat(10_000_000, st_blocks=0)) == 0


def test_posix_disk_bytes_fall_back_to_the_size() -> None:
    assert posix_disk_bytes("f", _stat(1234)) == 1234


def test_apparent_bytes_only_for_files_and_symlinks() -> None:
    def info(mode: int, size: int) -> os.stat_result:
        return cast(os.stat_result, SimpleNamespace(st_mode=mode, st_size=size))

    assert apparent_bytes(info(0o100644, 7)) == 7
    assert apparent_bytes(info(0o120777, 12)) == 12
    assert apparent_bytes(info(0o040755, 4096)) == 0
    assert apparent_bytes(info(0o010644, 5)) == 0
    assert apparent_bytes(info(0o100644, -1)) == 0


def test_a_reparse_point_is_a_link_only_when_it_names_another_path() -> None:
    attributes = 0x400
    assert is_link(_stat(0, st_file_attributes=attributes, st_reparse_tag=0xA0000003))
    assert is_link(_stat(0, st_file_attributes=attributes, st_reparse_tag=0xA000000C))
    assert not is_link(_stat(0, st_file_attributes=attributes, st_reparse_tag=0x9000001A))
    assert not is_link(_stat(0, st_file_attributes=0, st_reparse_tag=0xA0000003))


def test_disk_bytes_of_a_plain_file_cover_its_size(tmp_path: Path) -> None:
    write(tmp_path / "f.bin", os.urandom(10_000))
    usage = scan(tmp_path)
    assert usage.disk_bytes >= 10_000
    assert usage.disk_bytes - 10_000 < 1 << 20


@windows_only
def test_disk_bytes_follow_ntfs_allocation(tmp_path: Path) -> None:
    write(tmp_path / "a.bin", os.urandom(5000))
    write(tmp_path / "tiny.bin", b"x")
    big = scan(tmp_path / "a.bin").disk_bytes
    assert big >= 5000 and big % 512 == 0
    # A tiny file lives inside the file table and takes no cluster of its own.
    assert scan(tmp_path / "tiny.bin").disk_bytes < 512


@windows_only
def test_windows_falls_back_to_the_size_when_the_file_cannot_be_opened(tmp_path: Path) -> None:
    from dirsize._platform import disk_bytes

    target = write(tmp_path / "f.bin", b"z" * 700)
    info = os.stat(target)
    target.unlink()
    assert disk_bytes(str(target), info) == 700


@windows_only
def test_compressed_file_uses_less_than_its_size(tmp_path: Path) -> None:
    target = write(tmp_path / "c.bin", b"a" * (1 << 20))
    _run("compact", "/c", str(target))
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 1 << 20
    assert 0 < usage.disk_bytes < (1 << 20) // 2


@windows_only
def test_sparse_file_uses_almost_nothing(tmp_path: Path) -> None:
    target = write(tmp_path / "s.bin", b"")
    _run("fsutil", "sparse", "setflag", str(target))
    _run("fsutil", "file", "seteof", str(target), str(10 << 20))
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 10 << 20
    assert usage.disk_bytes < 1 << 20


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sparse files")
def test_posix_sparse_file_uses_less_than_its_size(tmp_path: Path) -> None:
    target = tmp_path / "s.bin"
    with target.open("wb") as handle:
        handle.truncate(10 << 20)
    if getattr(os.stat(target), "st_blocks", 0) * 512 >= 10 << 20:
        pytest.skip("this file system does not keep holes")
    assert scan(tmp_path).disk_bytes < 1 << 20
