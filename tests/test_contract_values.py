"""Stable value objects, signatures, argument errors and serialization."""

from __future__ import annotations

import inspect
import pickle
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

import dirsize as d

CALLS: list[Callable[..., object]] = [d.scan, d.iter_dirs, d.largest, d.dir_size, d.file_count]
VALUES = [
    d.Usage("p", 3, 4096, 1, 2, 0),
    d.DirUsage("p", 3, 4096, 1, 2, 0, 0, 1),
    d.FileUsage("p", 3, 4096),
]


def test_no_accidental_public_exports() -> None:
    assert {name for name in vars(d) if not name.startswith("_")} == set(d.__all__)
    assert get_args(d.Measure) == ("disk", "apparent")
    assert get_args(d.ErrorKind) == ("permission", "missing", "cycle", "other")


@pytest.mark.parametrize("value", VALUES)
def test_size_methods_validate_and_select(value: d.Usage | d.DirUsage | d.FileUsage) -> None:
    assert (value.size(), value.size("disk"), value.size("apparent")) == (4096, 4096, 3)
    with pytest.raises(ValueError, match="by must"):
        value.size("unknown")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [*VALUES, d.ScanError("p", "missing", "gone")])
def test_results_pickle_copy_compare_and_freeze(
    value: d.Usage | d.DirUsage | d.FileUsage | d.ScanError,
) -> None:
    assert type(value).__module__ == "dirsize"
    assert pickle.loads(pickle.dumps(value)) == value
    assert hash(pickle.loads(pickle.dumps(value))) == hash(value)
    with pytest.raises(FrozenInstanceError):
        value.path = "changed"  # type: ignore[misc]
    assert fields(value)[0].name == "path"


def test_usage_defaults_and_ok_are_independent() -> None:
    assert d.Usage("p", 0, 0, 0, 0, 0).ok
    assert not d.Usage("p", 0, 0, 0, 0, 0, measured=False).ok
    error = d.ScanError("p", "other", "error")
    assert not d.Usage("p", 0, 0, 0, 0, 0, (error,)).ok
    assert not d.FileUsage("p", 0, 0).is_link


@pytest.mark.parametrize("call", CALLS)
def test_signatures_defaults_and_type_hints(call: Callable[..., object]) -> None:
    parameters = inspect.signature(call).parameters
    names = ["path"]
    if call is d.largest:
        names += ["n", "by", "kind"]
        assert parameters["n"].default == 10
        assert parameters["by"].default == "disk"
        assert parameters["kind"].default == "file"
    names += ["follow_symlinks"]
    if call not in (d.dir_size, d.file_count):
        names += ["one_filesystem", "count_links"]
    if call in (d.scan, d.iter_dirs):
        names += ["include_dirs"]
    names += ["on_error"]
    assert list(parameters) == names
    for name in names:
        if name not in ("path", "n"):
            assert parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        if name in ("follow_symlinks", "one_filesystem", "count_links", "include_dirs"):
            assert parameters[name].default is False
    assert parameters["on_error"].default == (
        "raise" if call in (d.dir_size, d.file_count) else "ignore"
    )
    assert set(get_type_hints(call)) == {*names, "return"}


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("path", [b"bytes", 123, None, object()])
def test_bad_paths_fail_at_the_call(call: Callable[..., object], path: object) -> None:
    with pytest.raises(TypeError, match="path must"):
        call(path)


@pytest.mark.parametrize("call", CALLS)
def test_nul_and_bad_error_policy_fail_eagerly(call: Callable[..., object], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="NUL"):
        call("a\0b")
    with pytest.raises(ValueError, match="on_error") as caught:
        call(tmp_path, on_error="x" * 100_000)
    assert len(str(caught.value)) < 120


@pytest.mark.parametrize("n", [True, False, 1.0, "1", None])
def test_largest_rejects_non_integer_counts(n: object, tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="n must"):
        d.largest(tmp_path, n)  # type: ignore[call-overload]


def test_count_subclass_cannot_override_its_value(tmp_path: Path) -> None:
    class Count(int):
        def __int__(self) -> int:
            return 0

    (tmp_path / "file").write_bytes(b"a")
    assert len(d.largest(tmp_path, Count(1))) == 1


def test_zero_count_validates_options_without_reading(tmp_path: Path) -> None:
    assert d.largest(tmp_path / "missing", 0, on_error="raise") == []
    with pytest.raises(ValueError, match="kind"):
        d.largest(tmp_path, 0, kind="bad")  # type: ignore[call-overload]
