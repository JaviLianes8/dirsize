"""Total size and file count of a directory tree as one typed call."""

from __future__ import annotations

from ._core import OnError, dir_size, file_count

__version__ = "0.1.0"

__all__ = ["OnError", "dir_size", "file_count"]
