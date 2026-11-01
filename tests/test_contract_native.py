"""Windows allocation fallback and native handle ownership using synthetic handles."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import pytest

from dirsize import _platform, scan

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows allocation API")


@pytest.mark.parametrize("outcome", ["success", "failure", "exception"])
def test_allocation_queries_close_each_acquired_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"abcde")
    opened: list[int] = []
    closed: list[int] = []
    handle = 123
    problem = RuntimeError("query failure")

    def open_file(*args: object) -> int:
        opened.append(handle)
        return handle

    def query(h: int, kind: int, data: object, size: int) -> int:
        assert h == handle
        if outcome == "exception":
            raise problem
        if outcome == "failure":
            return 0
        pointer = ctypes.cast(data, ctypes.POINTER(ctypes.c_longlong))  # type: ignore[arg-type]
        pointer[0] = 4096
        return 1

    monkeypatch.setattr(_platform, "_open", open_file)
    monkeypatch.setattr(_platform, "_query", query)
    monkeypatch.setattr(_platform, "_close", closed.append)
    if outcome == "exception":
        with pytest.raises(RuntimeError) as caught:
            scan(path)
        assert caught.value is problem
    else:
        assert scan(path).disk_bytes == (4096 if outcome == "success" else 5)
    assert opened == closed == [handle]


def test_allocation_open_failure_uses_plain_size_without_closing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"abcde")
    closed: list[int] = []
    monkeypatch.setattr(_platform, "_open", lambda *args: _platform._INVALID_HANDLE)
    monkeypatch.setattr(_platform, "_close", closed.append)
    assert scan(path).disk_bytes == 5
    assert closed == []
