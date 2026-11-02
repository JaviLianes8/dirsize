"""Hand-written contracts for recursive state and importable exception families."""

from __future__ import annotations

import errno
import os
import pickle
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import dirsize as d

CALLS: list[Callable[..., object]] = [d.scan, d.iter_dirs, d.largest, d.dir_size, d.file_count]


class StorageError(OSError):
    pass


class Namespace:
    class StorageError(OSError):
        pass


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("call", CALLS)
def test_pickle_preserves_recursive_exception_attributes(
    call: Callable[..., object], protocol: int, tmp_path: Path
) -> None:
    missing = tmp_path / "absent"
    with pytest.raises(FileNotFoundError) as native:
        os.stat(missing)
    with pytest.raises(FileNotFoundError) as caught:
        result = call(missing, on_error="raise")
        if call is d.iter_dirs:
            assert isinstance(result, Iterator)
            list(result)

    for error in (native.value, caught.value):
        error.__dict__.update(detail=error, state={"error": error}, tag="value")
        restored = pickle.loads(pickle.dumps(error, protocol=protocol))
        assert restored.detail is restored
        assert restored.state["error"] is restored
        assert restored.tag == "value"
        assert restored.args == error.args
        assert restored.filename == error.filename
        assert restored.errno == error.errno
        if error is caught.value:
            assert isinstance(restored, FileNotFoundError)
            assert str(restored) == repr(restored) == str(error)


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("family", [StorageError, Namespace.StorageError])
def test_pickle_preserves_importable_exception_family(
    family: type[OSError], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = family(errno.EIO, "private detail", "first", None, "second")
    original.__dict__["detail"] = {"tag": "value"}
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    assert type(native) is family

    def fail(*args: object, **kwargs: object) -> None:
        raise original

    with monkeypatch.context() as patch:
        patch.setattr(os, "stat", fail)
        with pytest.raises(family) as caught:
            d.scan("synthetic", on_error="raise")

    restored = pickle.loads(pickle.dumps(caught.value, protocol=protocol))
    assert isinstance(restored, family)
    assert restored.args == original.args
    assert restored.__dict__ == original.__dict__
    for field in ("errno", "strerror", "filename", "filename2", "winerror"):
        assert getattr(restored, field, None) == getattr(original, field, None)
    assert str(restored) == repr(restored) == "other filesystem error (path redacted)"
