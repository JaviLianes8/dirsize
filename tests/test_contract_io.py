"""Streaming lifetime, error propagation and command line edge contracts."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from dirsize import iter_dirs, scan
from dirsize._cli import main


def test_closing_a_partial_walk_releases_all_listings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    real_scandir = os.scandir
    opened: list[str] = []
    closed: list[str] = []

    class Listing:
        def __init__(self, path: str) -> None:
            self.path = path
            self.entries = real_scandir(path)
            opened.append(path)

        def __iter__(self) -> Listing:
            return self

        def __next__(self) -> os.DirEntry[str]:
            return next(self.entries)

        def close(self) -> None:
            self.entries.close()
            closed.append(self.path)

    monkeypatch.setattr(os, "scandir", Listing)
    stream = iter_dirs(tmp_path)
    assert opened == []
    assert next(stream).depth == 2
    assert len(opened) == 3 and len(closed) == 1
    stream.close()
    assert set(opened) == set(closed)


def test_a_callback_exception_is_propagated_unchanged(tmp_path: Path) -> None:
    problem = RuntimeError("stop")

    def stop(error: OSError) -> None:
        raise problem

    with pytest.raises(RuntimeError) as caught:
        scan(tmp_path / "gone", on_error=stop)
    assert caught.value is problem


def test_root_junction_is_resolved_without_follow_option(tmp_path: Path) -> None:
    from helpers import junction

    target = tmp_path / "target"
    target.mkdir()
    (target / "f").write_bytes(b"abc")
    alias = junction(tmp_path / "alias", target)
    assert scan(alias).apparent_bytes == 3


def test_root_symlink_stat_is_resolved_before_selecting_file_or_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Synthetic symlink metadata keeps this contract runnable without link privileges.
    (tmp_path / "f").write_bytes(b"abc")
    original = os.stat

    def link_stat(path: str, *, follow_symlinks: bool = True) -> os.stat_result:
        actual = original(path, follow_symlinks=follow_symlinks)
        if os.fspath(path) == str(tmp_path) and not follow_symlinks:
            values = list(actual)
            values[0], values[6] = 0o120777, 99
            return os.stat_result(values)
        return actual

    monkeypatch.setattr(os, "stat", link_stat)
    usage = scan(tmp_path)
    assert usage.apparent_bytes == 3 and usage.files == 1


@pytest.mark.parametrize("mode", [["-s"], [], ["--top", "1"]])
def test_cli_repeated_file_root_is_counted_once(tmp_path: Path, mode: list[str]) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    output = io.StringIO()
    assert main([*mode, "-A", str(path), str(path)], out=output) == 0
    assert output.getvalue() == f"3\t{path}\n"
    output = io.StringIO()
    assert main([*mode, "-A", "-l", str(path), str(path)], out=output) == 0
    assert output.getvalue() == f"3\t{path}\n" * 2


def test_json_keeps_the_complete_schema_and_duplicate_roots(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    out = io.StringIO()
    assert main(["--json", str(path), str(path)], out=out) == 0
    result = json.loads(out.getvalue())
    assert set(result) == {"version", "paths"} and result["version"] == 1
    first, second = result["paths"]
    assert set(first) == {
        "path",
        "apparent_bytes",
        "disk_bytes",
        "files",
        "dirs",
        "links",
        "errors",
        "measured",
    }
    assert first["apparent_bytes"] == 3 and first["measured"]
    assert second == {
        "path": str(path),
        "apparent_bytes": 0,
        "disk_bytes": 0,
        "files": 0,
        "dirs": 0,
        "links": 0,
        "errors": [],
        "measured": False,
    }


def test_huge_cli_usage_error_is_bounded(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--top", "x" * 100_000])
    assert caught.value.code == 2
    assert len(capsys.readouterr().err) < 600


def test_overlapping_file_and_directory_roots_share_file_identity(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    out = io.StringIO()
    assert main(["-s", "-A", str(tmp_path), str(path)], out=out) == 0
    assert out.getvalue() == f"3\t{tmp_path}\n"
    out = io.StringIO()
    assert main(["-s", "-A", str(path), str(tmp_path)], out=out) == 0
    assert out.getvalue() == f"3\t{path}\n0\t{tmp_path}\n"


def test_closed_output_stream_returns_one(tmp_path: Path) -> None:
    output = io.StringIO()
    output.close()
    assert main(["-s", str(tmp_path)], out=output) == 1
