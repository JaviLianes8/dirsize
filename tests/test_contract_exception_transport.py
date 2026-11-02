"""Raised filesystem errors retain metadata and safe diagnostics across transport."""

from __future__ import annotations

import errno
import os
import pickle
import traceback
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import pytest

from dirsize import dir_size, scan

SECRET = "TOKEN_9c72_PRIVATE"
ERRORS = [
    FileNotFoundError(errno.ENOENT, SECRET, "first", None, "second"),
    PermissionError(errno.EACCES, SECRET, "first", None, "second"),
    NotADirectoryError(errno.ENOTDIR, SECRET, "first", None, "second"),
    OSError(errno.ELOOP, SECRET, "first", None, "second"),
    OSError(errno.EIO, SECRET, "first", None, "second"),
    OSError(SECRET),
]


def raised(error: OSError, monkeypatch: pytest.MonkeyPatch) -> OSError:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(os, "stat", fail)
        with pytest.raises(type(error)) as caught:
            scan("synthetic", on_error="raise")
    return caught.value


@pytest.mark.parametrize(
    "error", ERRORS, ids=["missing", "permission", "notdir", "loop", "io", "bare"]
)
def test_raised_errors_keep_original_args(error: OSError, monkeypatch: pytest.MonkeyPatch) -> None:
    assert raised(error, monkeypatch).args == error.args


@pytest.mark.parametrize(
    "field", ["errno", "strerror", "filename", "filename2", "winerror", "detail"]
)
def test_raised_errors_keep_explicit_metadata(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = FileNotFoundError(errno.ENOENT, SECRET, "first", None, "second")
    original.__dict__.update(winerror=2, detail={"input": SECRET})
    assert getattr(raised(original, monkeypatch), field) == getattr(original, field)


@pytest.mark.parametrize(
    ("error", "category"),
    list(zip(ERRORS, ["missing", "permission", "missing", "cycle", "other", "other"], strict=True)),
    ids=["missing", "permission", "notdir", "loop", "io", "bare"],
)
def test_raised_error_display_and_traceback_are_redacted(
    error: OSError, category: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    safe = raised(error, monkeypatch)
    expected = f"{category} filesystem error (path redacted)"
    assert str(safe) == repr(safe) == expected
    rendered = "".join(traceback.format_exception(type(safe), safe, safe.__traceback__))
    assert SECRET not in rendered
    assert expected in rendered


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize(
    "error", ERRORS, ids=["missing", "permission", "notdir", "loop", "io", "bare"]
)
def test_raised_errors_pickle_with_metadata_and_redaction(
    error: OSError, protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    error.__dict__["detail"] = {"input": SECRET}
    safe = raised(error, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert isinstance(restored, type(error))
    assert restored.args == error.args
    assert restored.__dict__ == error.__dict__
    for field in ("errno", "strerror", "filename", "filename2", "winerror"):
        assert getattr(restored, field, None) == getattr(error, field, None)
    assert str(restored) == repr(restored) == str(safe)
    assert SECRET not in str(restored)
    assert SECRET not in "".join(traceback.format_exception_only(type(restored), restored))
    assert str(pickle.loads(pickle.dumps(restored, protocol=protocol))) == str(safe)


def test_real_missing_file_error_round_trip(tmp_path: Path) -> None:
    missing = tmp_path / SECRET
    with pytest.raises(FileNotFoundError) as native:
        os.stat(missing)
    with pytest.raises(FileNotFoundError) as caught:
        dir_size(missing)
    assert caught.value.args == native.value.args
    restored = pickle.loads(pickle.dumps(caught.value))
    assert isinstance(restored, FileNotFoundError)
    assert restored.args == native.value.args
    assert restored.filename == str(missing)
    assert str(restored) == repr(restored) == "missing filesystem error (path redacted)"


def test_process_pool_propagates_filesystem_error(tmp_path: Path) -> None:
    missing = str(tmp_path / SECRET)
    with (
        ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool,
        pytest.raises(FileNotFoundError) as caught,
    ):
        pool.submit(dir_size, missing).result(timeout=60)
    error = caught.value
    assert error.filename == missing and error.errno == errno.ENOENT
    assert error.args == (error.errno, error.strerror)
    assert str(error) == repr(error) == "missing filesystem error (path redacted)"
    assert SECRET not in "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
