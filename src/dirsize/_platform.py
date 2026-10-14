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


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _StandardInfo(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", wintypes.DWORD),
            ("DeletePending", wintypes.BOOLEAN),
            ("Directory", wintypes.BOOLEAN),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _open = _kernel32.CreateFileW
    _open.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    _open.argtypes += [wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _open.restype = wintypes.HANDLE
    _query = _kernel32.GetFileInformationByHandleEx
    _query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _query.restype = wintypes.BOOL
    _close = _kernel32.CloseHandle
    _close.argtypes = [wintypes.HANDLE]
    _INVALID_HANDLE = wintypes.HANDLE(-1).value
    _READ_ATTRIBUTES, _SHARE_ALL, _OPEN_EXISTING = 0x80, 0x7, 3
    _BACKUP_SEMANTICS, _FILE_STANDARD_INFO = 0x02000000, 1

    def windows_disk_bytes(path: str, info: os.stat_result) -> int:
        """``AllocationSize`` from ``FILE_STANDARD_INFO``: compressed and sparse aware.

        Opening for attributes only never reads data. A link or directory reports 0:
        its data lives in the file system's own tables. On failure, the plain size.
        """
        if not stat.S_ISREG(info.st_mode) or is_link(info):
            return 0
        handle = _open(
            path, _READ_ATTRIBUTES, _SHARE_ALL, None, _OPEN_EXISTING, _BACKUP_SEMANTICS, None
        )
        if handle is None or handle == _INVALID_HANDLE:
            return info.st_size
        try:
            data = _StandardInfo()
            if not _query(handle, _FILE_STANDARD_INFO, ctypes.byref(data), ctypes.sizeof(data)):
                return info.st_size
            allocated: int = data.AllocationSize
            return max(0, allocated)
        finally:
            _close(handle)

    disk_bytes: Callable[[str, os.stat_result], int] = windows_disk_bytes
else:
    disk_bytes = posix_disk_bytes
