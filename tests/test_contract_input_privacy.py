"""Hand-written malformed inputs and native Windows path validation boundaries."""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable

import pytest

import dirsize as d

CALLS: list[Callable[..., object]] = [d.scan, d.iter_dirs, d.largest, d.dir_size, d.file_count]
SECRET = "TOKEN_9c72_PRIVATE"


class Hostile:
    def __repr__(self) -> str:
        raise AssertionError("repr must not run")


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("family", [RuntimeError, ValueError, OSError])
def test_non_typeerror_pathlike_failure_propagates_unchanged(
    call: Callable[..., object], family: type[Exception]
) -> None:
    original = family("path conversion failed")

    class BrokenPath:
        def __fspath__(self) -> str:
            raise original

    with pytest.raises(family) as caught:
        call(BrokenPath())
    assert caught.value is original


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("result", [None, 123, b"private"], ids=["none", "int", "bytes"])
def test_malformed_pathlike_diagnostics_are_private(
    call: Callable[..., object], result: object
) -> None:
    malformed = type(SECRET, (), {"__fspath__": lambda self: result})()
    with pytest.raises(TypeError) as caught:
        call(malformed)
    assert str(caught.value) == "path must be a str or os.PathLike[str]"
    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert SECRET not in rendered


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize(
    "value", [SECRET.encode() * 1000, Hostile(), None], ids=["bytes", "repr", "none"]
)
def test_invalid_paths_have_bounded_private_diagnostics(
    call: Callable[..., object], value: object
) -> None:
    with pytest.raises(TypeError) as caught:
        call(value)
    assert SECRET not in str(caught.value)
    assert len(str(caught.value)) < 100


@pytest.mark.parametrize("value", [SECRET * 1000, Hostile()], ids=["text", "repr"])
def test_invalid_counts_have_bounded_private_diagnostics(value: object) -> None:
    with pytest.raises(TypeError) as caught:
        d.largest(".", n=value)  # type: ignore[call-overload]
    assert SECRET not in str(caught.value)
    assert len(str(caught.value)) < 100


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path boundary")
@pytest.mark.parametrize("units", [32766, 32767, 32768])
@pytest.mark.parametrize("astral", [False, True])
def test_windows_utf16_boundary_is_inclusive(units: int, astral: bool) -> None:
    path = "\U0001f600" * (units // 2) + "x" * (units % 2) if astral else "x" * units
    if units > 32767:
        with pytest.raises(ValueError, match="maximum 32767 UTF-16 code units"):
            d.iter_dirs(path, on_error="ignore")
    else:
        iterator = d.iter_dirs(path, on_error="ignore")
        iterator.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows surrogate paths")
@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"], ids=["high", "low"])
def test_windows_surrogate_path_reaches_error_policy(surrogate: str) -> None:
    path = "absent-" + surrogate
    errors: list[OSError] = []
    iterator = d.iter_dirs(path, on_error=errors.append)
    assert errors == []
    assert list(iterator) == []
    assert len(errors) == 1 and errors[0].filename == path
