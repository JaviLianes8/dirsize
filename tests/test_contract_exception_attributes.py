"""Hand-written contracts for attached exception values and shared identity."""

from __future__ import annotations

import errno
import os
import pickle
from collections.abc import Callable, Iterator

import pytest

import dirsize as d

pytestmark = [
    pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1)),
    pytest.mark.parametrize("call", [d.scan, d.iter_dirs, d.largest, d.dir_size, d.file_count]),
]


def _raised(
    original: OSError, call: Callable[..., object], monkeypatch: pytest.MonkeyPatch
) -> OSError:
    def fail(*args: object, **kwargs: object) -> None:
        raise original

    with monkeypatch.context() as patch:
        patch.setattr(os, "stat", fail)
        with pytest.raises(OSError) as caught:
            result = call("synthetic", on_error="raise")
            if call is d.iter_dirs:
                assert isinstance(result, Iterator)
                list(result)
    return caught.value


@pytest.mark.parametrize("value", [0, False, "", None, [], {}, set(), ()])
def test_pickle_preserves_false_valued_exception_attributes(
    value: object, call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    original.__dict__["detail"] = value
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert "detail" in restored.__dict__
    assert restored.detail == native.detail == value
    assert type(restored.detail) is type(native.detail) is type(value)


def test_pickle_preserves_private_exception_attributes(
    call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    original.__dict__["_detail"] = "custom attribute"
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert restored._detail == native._detail == "custom attribute"


def test_pickle_preserves_exception_notes(
    call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    add_note = getattr(original, "add_note", None)
    if add_note is None:
        pytest.skip("exception notes require Python 3.11 or newer")
    add_note("first note")
    add_note("second note")
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert restored.__notes__ == native.__notes__ == ["first note", "second note"]
    assert type(restored.__notes__) is list


@pytest.mark.parametrize(
    "value",
    [[1, 2], {1, 2}, (1, 2), b"binary\xff", bytearray(b"mutable\xff"), frozenset({1, 2}), 1.75],
    ids=["list", "set", "tuple", "bytes", "bytearray", "frozenset", "float"],
)
def test_pickle_preserves_exception_container_values_and_types(
    value: object, call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    original.__dict__["detail"] = value
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert type(restored.detail) is type(native.detail) is type(value)
    assert restored.detail == native.detail == value


def test_pickle_preserves_shared_exception_dictionaries(
    call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    shared = {"value": 7}
    original.__dict__.update(first=shared, second=shared)
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    assert native.first is native.second
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert restored.first == restored.second == native.first == shared
    assert restored.first is restored.second


@pytest.mark.parametrize("shared", [[1, 2, 3], {1, 2, 3}], ids=["list", "set"])
def test_pickle_preserves_shared_exception_lists_and_sets(
    shared: object, call: Callable[..., object], protocol: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = OSError(errno.EIO, "attached state")
    original.__dict__.update(first=shared, second=shared)
    native = pickle.loads(pickle.dumps(original, protocol=protocol))
    assert native.first is native.second
    safe = _raised(original, call, monkeypatch)
    restored = pickle.loads(pickle.dumps(safe, protocol=protocol))
    assert type(restored.first) is type(native.first) is type(shared)
    assert restored.first == restored.second == native.first == shared
    assert restored.first is restored.second
