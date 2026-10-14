"""What one entry occupies on disk, and whether it is a link, on each platform."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Callable

# IsReparseTagNameSurrogate: the tag names another entity (symlink, junction, mount point).
_NAME_SURROGATE = 0x20000000
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT


def is_link(info: os.stat_result) -> bool:
    """True for a symlink, or on Windows for any reparse point that names another path."""
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0) or 0
    tag = getattr(info, "st_reparse_tag", 0) or 0
    return bool(attributes & _REPARSE_POINT) and bool(tag & _NAME_SURROGATE)


def apparent_bytes(info: os.stat_result) -> int:
    """``st_size`` of a regular file or symlink; 0 for anything else, as GNU du counts it."""
    if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        return max(0, info.st_size)
    return 0


def posix_disk_bytes(path: str, info: os.stat_result) -> int:
    """Allocated bytes from ``st_blocks``, which counts 512-byte units."""
    blocks = getattr(info, "st_blocks", None)
    return info.st_size if blocks is None else blocks * 512


def _round_up(size: int, unit: int) -> int:
    return -(-size // unit) * unit if unit > 0 else size


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _compressed_size = _kernel32.GetCompressedFileSizeW
    _compressed_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    _compressed_size.restype = wintypes.DWORD
    _volume_path = _kernel32.GetVolumePathNameW
    _volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _volume_path.restype = wintypes.BOOL
    _free_space = _kernel32.GetDiskFreeSpaceW
    _free_space.argtypes = [wintypes.LPCWSTR] + [ctypes.POINTER(wintypes.DWORD)] * 4
    _free_space.restype = wintypes.BOOL
    _INVALID = 0xFFFFFFFF
    _clusters: dict[int, int] = {}

    def _cluster_size(path: str, device: int) -> int:
        if device in _clusters:
            return _clusters[device]
        buffer = ctypes.create_unicode_buffer(32768)
        size = 0
        if _volume_path(path, buffer, len(buffer)):
            sectors, per_sector, free, total = (wintypes.DWORD() for _ in range(4))
            if _free_space(buffer.value, sectors, per_sector, free, total):
                size = sectors.value * per_sector.value
        _clusters[device] = size
        return size

    def windows_disk_bytes(path: str, info: os.stat_result) -> int:
        """Compressed or sparse allocation from ``GetCompressedFileSizeW``, in whole clusters.

        A link or directory reports 0: its data lives in the file system's own tables.
        """
        if not stat.S_ISREG(info.st_mode) or is_link(info):
            return 0
        high = wintypes.DWORD(0)
        ctypes.set_last_error(0)
        low = _compressed_size(path, ctypes.byref(high))
        if low == _INVALID and ctypes.get_last_error() != 0:
            return info.st_size
        return _round_up((high.value << 32) | low, _cluster_size(path, info.st_dev))

    disk_bytes: Callable[[str, os.stat_result], int] = windows_disk_bytes
else:
    disk_bytes = posix_disk_bytes
