"""Root failures and diagnostic privacy contracts with synthetic error inputs."""

from __future__ import annotations

import io
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import dirsize as d
from dirsize import _state
from dirsize._cli import main

CALLS: list[Callable[..., object]] = [d.scan, d.iter_dirs, d.largest, d.dir_size, d.file_count]
SECRET = "TOKEN_9c72_PRIVATE"


@pytest.mark.parametrize("include_dirs", [False, True])
def test_unlistable_root_is_unmeasured_with_zero_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_dirs: bool
) -> None:
    def denied(path: str) -> None:
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(os, "scandir", denied)
    monkeypatch.setattr(_state, "disk_bytes", lambda path, info: 4096)
    errors: list[OSError] = []
    usage = d.scan(tmp_path, include_dirs=include_dirs, on_error=errors.append)
    assert not usage.measured and not usage.ok
    assert (usage.apparent_bytes, usage.disk_bytes, usage.files, usage.dirs, usage.links) == (
        0,
        0,
        0,
        0,
        0,
    )
    assert len(errors) == len(usage.errors) == 1
    assert usage.errors[0].kind == "permission"
    out = io.StringIO()
    assert main(["--json", str(tmp_path)], out=out) == 1
    result = json.loads(out.getvalue())["paths"][0]
    assert result["measured"] is False and result["disk_bytes"] == 0
    assert result["errors"][0]["kind"] == "permission"


def test_cli_top_zero_reports_missing_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = io.StringIO()
    assert main(["--top", "0", str(tmp_path / "missing")], out=out) == 1
    assert out.getvalue() == ""
    assert capsys.readouterr().err.startswith("dirsize: ")


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("pathlike", [False, True])
def test_path_string_subclasses_use_their_text(
    call: Callable[..., object], tmp_path: Path, pathlike: bool
) -> None:
    class Text(str):
        def __contains__(self, value: object) -> bool:
            raise RuntimeError("membership hook")

        def __str__(self) -> str:
            raise RuntimeError("string hook")

    class PathText:
        def __fspath__(self) -> str:
            return Text(str(tmp_path))

    actual = call(PathText() if pathlike else Text(str(tmp_path)))
    expected = call(tmp_path)
    assert list(actual) == list(expected) if call is d.iter_dirs else actual == expected  # type: ignore[call-overload]


@pytest.mark.parametrize("option", ["by", "kind", "on_error"])
def test_invalid_options_do_not_echo_values(option: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError) as caught:
        d.largest(tmp_path, **{option: SECRET})  # type: ignore[call-overload]
    assert SECRET not in str(caught.value)
    assert option in str(caught.value)


@pytest.mark.parametrize("args", [["--top", SECRET], ["--" + SECRET], ["--json=" + SECRET]])
def test_cli_usage_errors_do_not_echo_values(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        main(args)
    assert caught.value.code == 2
    message = capsys.readouterr().err
    assert SECRET not in message and len(message) < 600


@pytest.mark.parametrize("suffix", [SECRET, "x" * 10_000], ids=["secret", "long"])
def test_filesystem_diagnostics_redact_paths_but_keep_metadata(
    suffix: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(tmp_path / suffix)
    with pytest.raises(OSError) as original:
        os.stat(path)
    with pytest.raises(type(original.value)) as caught:
        d.scan(path, on_error="raise")
    assert caught.value.filename == path
    assert caught.value.errno == original.value.errno
    assert getattr(caught.value, "winerror", None) == getattr(original.value, "winerror", None)
    assert suffix not in str(caught.value) and len(str(caught.value)) < 300
    assert suffix not in repr(caught.value) and len(repr(caught.value)) < 300
    out = io.StringIO()
    assert main(["-s", path], out=out) == 1
    diagnostic = capsys.readouterr().err
    assert suffix not in diagnostic and len(diagnostic) < 300
    assert d.scan(path).errors[0].path == path


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path boundary")
@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("text", ["x" * 100_000, "\U0001f600" * 20_000], ids=["ascii", "utf16"])
def test_windows_overlong_paths_fail_eagerly(call: Callable[..., object], text: str) -> None:
    with pytest.raises(ValueError, match=r"path.*long"):
        call(text, on_error="ignore")


def test_regular_file_roots_have_synthetic_directory_totals(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"abc")
    streamed = list(d.iter_dirs(path))
    assert streamed == d.largest(path, kind="dir")
    assert len(streamed) == 1
    result = streamed[0]
    assert result.path == str(path) and result.apparent_bytes == 3
    assert (result.files, result.dirs, result.links, result.errors, result.depth) == (1, 0, 0, 0, 0)
