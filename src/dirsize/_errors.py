"""Errors met during a walk: their typed record and the ``on_error`` policy."""

from __future__ import annotations

import errno
import os
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module

from ._types import ErrorHandler, ErrorKind, OnError

# ERROR_CANT_RESOLVE_FILENAME: what Windows reports for a symlink loop (POSIX says ELOOP).
_CANT_RESOLVE = 1921


@dataclass(frozen=True)
class ScanError:
    """One path that could not be measured, and why.

    ``kind`` is ``"permission"``, ``"missing"`` (vanished, not a directory, or a
    dangling link met while following links), ``"cycle"`` (a directory met again
    inside itself without following links, or a link that loops back to itself
    while following links) or ``"other"``. ``message`` is the system's own text.

    >>> import errno
    >>> error = PermissionError(errno.EACCES, "Permission denied", "secret")
    >>> ScanError.from_os_error(error)
    ScanError(path='secret', kind='permission', message='Permission denied')
    """

    path: str
    kind: ErrorKind
    message: str

    @classmethod
    def from_os_error(cls, error: OSError) -> ScanError:
        """Classify ``error`` and keep its path and message.

        >>> ScanError.from_os_error(FileNotFoundError(2, "No such file", "gone")).kind
        'missing'
        """
        return cls(path=_error_path(error), kind=_kind(error), message=error.strerror or str(error))


def as_handler(on_error: OnError) -> ErrorHandler:
    """Turn the public ``on_error`` value into a callable, rejecting anything else."""
    if callable(on_error):
        return on_error
    if isinstance(on_error, str) and str.__str__(on_error) == "raise":
        return _raise
    if isinstance(on_error, str) and str.__str__(on_error) == "ignore":
        return _ignore
    raise ValueError("on_error must be 'raise', 'ignore' or a callable")


def cycle_error(path: str) -> OSError:
    """Build the error reported when a directory turns up again inside itself."""
    return OSError(errno.ELOOP, "circular directory structure", path)


def _raise(error: OSError) -> None:
    safe = _restore_error(type(error), error.args, error.__dict__, _metadata(error))
    raise safe from None


def _metadata(error: OSError) -> dict[str, object]:
    return {
        name: getattr(error, name)
        for name in ("errno", "strerror", "filename", "filename2", "winerror")
        if hasattr(error, name)
    }


def _restore_error(
    family: type[OSError],
    args: tuple[object, ...],
    attributes: dict[str, object],
    metadata: dict[str, object],
) -> OSError:
    # Retain the exception family and explicit metadata without printing input paths.
    kind = type(
        family.__name__,
        (family,),
        {"__str__": diagnostic, "__repr__": diagnostic, "__reduce__": _reduce_error},
    )
    safe: OSError = OSError.__new__(kind)
    safe.args = args
    safe.__dict__.update(attributes)
    for name, value in metadata.items():
        setattr(safe, name, value)
    return safe


def _reduce_error(
    error: OSError,
) -> tuple[Callable[..., OSError], tuple[object, ...], dict[str, object]]:
    # Names avoid old pickle protocols mapping newer OSError families to OSError.
    family = type(error).__bases__[0]
    # Deferred state restores back-references after pickle memoizes the exception.
    return (
        _unpickle_error,
        (
            family.__module__,
            family.__qualname__,
            error.args,
            {},
            _metadata(error),
        ),
        error.__dict__,
    )


def _unpickle_error(
    module: str,
    qualname: str,
    args: tuple[object, ...],
    attributes: dict[str, object],
    metadata: dict[str, object],
) -> OSError:
    family: object = import_module(module)
    for name in qualname.split("."):
        family = getattr(family, name)
    if not isinstance(family, type) or not issubclass(family, OSError):
        raise TypeError("expected an OSError family")
    return _restore_error(family, args, attributes, metadata)


def diagnostic(error: OSError) -> str:
    """A bounded description containing no filesystem-supplied text or paths."""
    return f"{_kind(error)} filesystem error (path redacted)"


def _ignore(error: OSError) -> None:
    return None


def _error_path(error: OSError) -> str:
    name = error.filename
    if isinstance(name, bytes):
        return os.fsdecode(name)
    return "" if name is None else str(name)


def _kind(error: OSError) -> ErrorKind:
    if isinstance(error, PermissionError):
        return "permission"
    if isinstance(error, (FileNotFoundError, NotADirectoryError)):
        return "missing"
    if error.errno == errno.ELOOP or getattr(error, "winerror", None) == _CANT_RESOLVE:
        return "cycle"
    return "other"
