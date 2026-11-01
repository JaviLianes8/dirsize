"""Live GNU program oracles and fetched references, with no vendored third-party text."""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import sparse

from dirsize import scan
from dirsize._human import human


def _program(name: str) -> str:
    found = os.environ.get(f"DIRSIZE_{name.upper()}") or shutil.which(name)
    if not found:
        pytest.skip(f"set DIRSIZE_{name.upper()} to a GNU {name} executable")
    version = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=30)
    if "GNU coreutils" not in version.stdout:
        pytest.skip(f"{name} is not GNU coreutils")
    return found


def _du(root: Path, *flags: str) -> int:
    result = subprocess.run(
        [_program("du"), *flags, root.as_posix()],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return int(result.stdout.split("\t")[0])


@pytest.mark.parametrize("seed", [18, 102, 20261101])
def test_live_gnu_du_matches_seeded_tree_sizes(tmp_path: Path, seed: int) -> None:
    _program("du")
    rng = random.Random(seed)
    for i in range(24):
        folder = tmp_path / str(i % 4)
        folder.mkdir(exist_ok=True)
        (folder / str(i)).write_bytes(rng.randbytes(rng.randrange(100_000)))
    os.link(tmp_path / "0" / "0", tmp_path / "hardlink")
    for count in (False, True):
        flags = ["-l"] if count else []
        usage = scan(tmp_path, count_links=count, include_dirs=True)
        assert usage.apparent_bytes == _du(tmp_path, "-sb", *flags)
        assert usage.disk_bytes == _du(tmp_path, "-sB1", *flags)


def test_live_du_agrees_on_sparse_files(tmp_path: Path) -> None:
    _program("du")
    target = sparse(tmp_path / "hole", 8 << 20)
    usage = scan(target)
    assert usage.apparent_bytes == _du(target, "-sb")
    assert usage.disk_bytes == _du(target, "-sB1")


def test_live_gnu_numfmt_matches_integer_rounding() -> None:
    program = _program("numfmt")
    rng = random.Random(20261101)
    sizes = [0, 1023, 1024, 1025, 10239, 1048575, (1 << 60) + 1]
    sizes += [rng.randrange(1 << 63) for _ in range(2000)]
    result = subprocess.run(
        [program, "--to=iec", "--round=up"],
        input=("\n".join(map(str, sizes)) + "\n").encode(),
        capture_output=True,
        timeout=30,
        check=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    assert [human(n) for n in sizes] == result.stdout.decode().splitlines()


def test_fetched_sources_match_the_recorded_manifest() -> None:
    directory = os.environ.get("DIRSIZE_REFERENCES")
    if not directory:
        pytest.skip("set DIRSIZE_REFERENCES after scripts/fetch_references.py")
    sources = json.loads(Path(__file__).with_name("references.json").read_text(encoding="utf-8"))
    for item in sources:
        data = (Path(directory) / item["name"]).read_bytes()
        assert len(data) == item["size"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]


def test_walk_comparison_revisits_a_junction(tmp_path: Path) -> None:
    from helpers import junction

    (tmp_path / "f").write_bytes(b"x")
    junction(tmp_path / "loop", tmp_path)
    walk = os.walk(tmp_path)
    try:
        rows = [next(walk) for _ in range(4)]
    finally:
        walk.close()  # type: ignore[attr-defined]
    assert all("f" in files for _, _, files in rows)
    assert scan(tmp_path).apparent_bytes == 1
