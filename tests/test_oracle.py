"""GNU du as a test-only oracle on seeded random trees (POSIX with GNU coreutils).

``du`` is used when it reports GNU coreutils, else ``gnudu`` (Ubuntu ships the GNU
build under that name next to the uutils port). Without either the module skips.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dirsize import iter_dirs, scan


def _gnu_du() -> str | None:
    if sys.platform == "win32":
        return None
    for name in ("du", "gnudu"):
        found = shutil.which(name)
        if found is None:
            continue
        version = subprocess.run([found, "--version"], capture_output=True, text=True)
        if "GNU coreutils" in version.stdout:
            return found
    return None


DU = _gnu_du()
pytestmark = pytest.mark.skipif(DU is None, reason="GNU du is not installed")
SEEDS = range(12)


def _build(root: Path, seed: int) -> None:
    rng = random.Random(seed)
    dirs = [root]
    files: list[Path] = []
    for index in range(rng.randint(15, 40)):
        parent = rng.choice(dirs)
        roll = rng.random()
        if roll < 0.25:
            child = parent / f"d{index}"
            child.mkdir()
            dirs.append(child)
        elif roll < 0.7:
            path = parent / f"f{index}"
            path.write_bytes(os.urandom(rng.choice([0, 1, 511, 4096, 5000, 70_000])))
            files.append(path)
        elif roll < 0.8 and files:
            os.link(rng.choice(files), parent / f"h{index}")
        elif roll < 0.88:
            with (parent / f"s{index}").open("wb") as handle:
                handle.truncate(rng.choice([1 << 16, 1 << 20]))
        elif roll < 0.94 and files:
            os.symlink(rng.choice(files), parent / f"l{index}")
        elif len(dirs) > 1:
            target = rng.choice(dirs[1:])
            if parent != target and target not in parent.parents:
                os.symlink(target, parent / f"ld{index}", target_is_directory=True)


def _tree(tmp_path: Path, seed: int) -> Path:
    root = tmp_path / "tree"
    root.mkdir()
    _build(root, seed)
    return root


def _du(*args: str) -> dict[str, int]:
    assert DU is not None
    done = subprocess.run([DU, *args], capture_output=True, text=True, check=True)
    rows = (line.split("\t", 1) for line in done.stdout.splitlines())
    return {path: int(size) for size, path in rows}


@pytest.mark.parametrize("seed", SEEDS)
def test_totals_match_gnu_du(tmp_path: Path, seed: int) -> None:
    root = _tree(tmp_path, seed)
    usage = scan(root, include_dirs=True)
    assert usage.ok
    assert usage.apparent_bytes == _du("-sb", str(root))[str(root)]
    assert usage.disk_bytes == _du("-sB1", str(root))[str(root)]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_directory_matches_gnu_du(tmp_path: Path, seed: int) -> None:
    root = _tree(tmp_path, seed)
    dirs = list(iter_dirs(root, include_dirs=True))
    assert {d.path: d.apparent_bytes for d in dirs} == _du("-b", str(root))
    assert {d.path: d.disk_bytes for d in dirs} == _du("-B1", str(root))


@pytest.mark.parametrize("seed", SEEDS)
def test_count_links_matches_du_l(tmp_path: Path, seed: int) -> None:
    root = _tree(tmp_path, seed)
    usage = scan(root, include_dirs=True, count_links=True)
    assert usage.apparent_bytes == _du("-sbl", str(root))[str(root)]
    assert usage.disk_bytes == _du("-sl", "-B1", str(root))[str(root)]


@pytest.mark.parametrize("seed", SEEDS)
def test_follow_symlinks_matches_du_capital_l(tmp_path: Path, seed: int) -> None:
    root = _tree(tmp_path, seed)
    usage = scan(root, include_dirs=True, follow_symlinks=True)
    assert usage.apparent_bytes == _du("-sbL", str(root))[str(root)]
    assert usage.disk_bytes == _du("-sL", "-B1", str(root))[str(root)]
