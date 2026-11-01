"""Size of a directory tree, apparent and on disk, as typed calls and a ``du``-like CLI.

Three type aliases name the accepted values: ``Measure`` is what ``by`` takes,
``ErrorKind`` is the ``kind`` of a :class:`ScanError`, and ``OnError`` is what
``on_error`` takes (two names or a callable that receives each ``OSError``).

>>> import typing
>>> from dirsize import ErrorKind, Measure, OnError
>>> typing.get_args(Measure)
('disk', 'apparent')
>>> typing.get_args(ErrorKind)
('permission', 'missing', 'cycle', 'other')
>>> policy: OnError = "raise"
>>> errors: list[OSError] = []
>>> policy = errors.append
"""

from __future__ import annotations

from ._core import dir_size, file_count, iter_dirs, scan
from ._errors import ScanError
from ._largest import largest
from ._results import DirUsage, FileUsage, Usage
from ._types import ErrorKind, Measure, OnError

del annotations

__version__ = "1.0.0"

# Pickles name a class by its module: point them at the public one, which never moves.
for _public in (DirUsage, FileUsage, ScanError, Usage):
    _public.__module__ = __name__
del _public

__all__ = [
    "DirUsage",
    "ErrorKind",
    "FileUsage",
    "Measure",
    "OnError",
    "ScanError",
    "Usage",
    "dir_size",
    "file_count",
    "iter_dirs",
    "largest",
    "scan",
]
