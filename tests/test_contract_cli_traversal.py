"""CLI validation and complete traversal when no result rows are requested."""

from __future__ import annotations

import errno
import io
import os
import sys
from pathlib import Path

import pytest

from dirsize._cli import main


def test_cli_top_zero_reports_error_after_first_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "file").write_bytes(b"abc")
    with os.scandir(tmp_path) as listing:
        entry = next(listing)
    events: list[str] = []

    class FailingListing:
        def __iter__(self) -> FailingListing:
            return self

        def __next__(self) -> os.DirEntry[str]:
            if not events:
                events.append("file")
                return entry
            events.append("error")
            raise OSError(errno.EIO, "read failed", str(tmp_path))

        def close(self) -> None:
            events.append("closed")

    monkeypatch.setattr(os, "scandir", lambda path: FailingListing())
    out = io.StringIO()
    assert main(["--top", "0", str(tmp_path)], out=out) == 1
    assert events == ["file", "error", "closed"]
    assert out.getvalue() == ""
    assert capsys.readouterr().err == "dirsize: other filesystem error (path redacted)\n"


@pytest.mark.parametrize("mode", [[], ["--top", "0"], ["--json"], ["-s"]])
@pytest.mark.parametrize("overlong", [False, True], ids=["nul", "long"])
def test_cli_invalid_paths_have_bounded_usage_errors(
    mode: list[str], overlong: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    if overlong and sys.platform != "win32":
        pytest.skip("Windows path boundary")
    secret = "TOKEN_9c72_PRIVATE"
    path = secret + ("x" * 32768 if overlong else "\0suffix")
    out = io.StringIO()
    with pytest.raises(SystemExit) as caught:
        main([*mode, path], out=out)
    assert caught.value.code == 2 and out.getvalue() == ""
    message = capsys.readouterr().err
    assert "usage:" in message
    assert secret not in message and len(message) < 600
