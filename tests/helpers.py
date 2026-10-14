"""Builders for real temporary trees: files, hard links, junctions, symlinks, locked folders."""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def hardlink(link: Path, target: Path) -> Path:
    """Create a hard link, or skip when the file system cannot."""
    try:
        os.link(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"hard links not supported here: {exc}")
    if link.stat().st_nlink <= 1 or link.stat().st_ino == 0:
        pytest.skip("this file system does not report hard link metadata")
    return link


def junction(link: Path, target: Path) -> Path:
    """Create a Windows directory junction, or skip the test elsewhere."""
    if sys.platform != "win32":
        pytest.skip("junctions exist only on Windows")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))
    return link


def symlink(link: Path, target: Path) -> Path:
    """Create a symlink, or skip when the platform or account does not allow it."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks not permitted here: {exc}")
    return link


@contextmanager
def unreadable(path: Path) -> Iterator[None]:
    """Deny listing ``path`` to the current user for the duration of the block."""
    if sys.platform == "win32":
        user = os.environ.get("USERNAME") or getpass.getuser()
        subprocess.run(
            ["icacls", str(path), "/deny", f"{user}:(RD)"], check=True, capture_output=True
        )
        try:
            _require_denied(path)
            yield
        finally:
            subprocess.run(
                ["icacls", str(path), "/remove:d", user], check=True, capture_output=True
            )
    else:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("root can read anything")
        mode = path.stat().st_mode
        path.chmod(0)
        try:
            _require_denied(path)
            yield
        finally:
            path.chmod(mode)


def _require_denied(path: Path) -> None:
    # An elevated account holding the backup privilege still lists the folder.
    try:
        os.listdir(path)
    except PermissionError:
        return
    pytest.skip("this account can read a folder it was denied")
