"""Complete escaped output and immediate visibility of command line errors."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dirsize import Usage, _cli
from dirsize._core import measure
from dirsize._state import Seen
from dirsize._types import ErrorHandler, WalkOptions


def test_ascii_stdout_preserves_complete_escaped_filename(tmp_path: Path) -> None:
    target = tmp_path / "caf\u00e9"
    target.write_bytes(b"abc")
    env = dict(
        os.environ,
        PYTHONIOENCODING="ascii:strict",
        PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
    )
    result = subprocess.run(
        [sys.executable, "-B", "-m", "dirsize", "-s", "-A", str(target)],
        env=env,
        capture_output=True,
        timeout=300,
    )
    expected = f"3\t{target}\n".encode("ascii", "backslashreplace")
    assert result.returncode == 0 and result.stderr == b""
    assert result.stdout.replace(b"\r\n", b"\n") == expected


def test_cli_errors_are_flushed_before_next_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Buffered(io.StringIO):
        visible = ""

        def flush(self) -> None:
            self.visible = self.getvalue()

    stream = Buffered()
    monkeypatch.setattr(sys, "stderr", stream)
    observed: list[str] = []

    def watching(path: str, options: WalkOptions, handle: ErrorHandler, seen: Seen) -> Usage:
        if path == str(tmp_path):
            observed.append(stream.visible)
        return measure(path, options, handle, seen)

    monkeypatch.setattr(_cli, "measure", watching)
    assert _cli.main(["-s", str(tmp_path / "gone"), str(tmp_path)], out=io.StringIO()) == 1
    assert len(observed) == 1 and observed[0].startswith("dirsize: ")
