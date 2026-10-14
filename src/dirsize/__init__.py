"""Size of a directory tree, apparent and on disk, as typed calls and a ``du``-like CLI."""

from __future__ import annotations

from ._core import dir_size, file_count, iter_dirs, largest, scan
from ._types import DirUsage, ErrorKind, FileUsage, Measure, OnError, ScanError, Usage

__version__ = "0.2.0"

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
