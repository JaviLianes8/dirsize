"""Seeded generated trees and hostile arguments; these are hand-built properties."""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

from dirsize import dir_size, file_count, iter_dirs, largest, scan


@pytest.mark.parametrize("seed", [7, 42, 20261101])
def test_seeded_trees_match_an_independent_flat_inventory(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    directories = [tmp_path]
    sizes: dict[Path, int] = {}
    for index in range(180):
        parent = rng.choice(directories)
        path = parent / f"entry-{index}"
        if rng.randrange(5) == 0:
            path.mkdir()
            directories.append(path)
        else:
            size = rng.randrange(5000)
            path.write_bytes(bytes([rng.randrange(256)]) * size)
            sizes[path] = size
    expected = sum(sizes.values())
    usage = scan(tmp_path)
    assert (usage.apparent_bytes, usage.files, usage.dirs, usage.links) == (
        expected,
        len(sizes),
        len(directories) - 1,
        0,
    )
    assert usage.ok and dir_size(tmp_path) == expected and file_count(tmp_path) == len(sizes)
    for folder in iter_dirs(tmp_path):
        prefix = Path(folder.path)
        assert folder.apparent_bytes == sum(n for p, n in sizes.items() if prefix in p.parents)
    top = largest(tmp_path, 17, by="apparent")
    assert [i.apparent_bytes for i in top] == sorted(sizes.values(), reverse=True)[:17]
    original = next(iter(sizes))
    os.link(original, tmp_path / "extra-link")
    assert scan(tmp_path).apparent_bytes == expected
    assert scan(tmp_path, count_links=True).apparent_bytes == expected + sizes[original]
    assert file_count(tmp_path) == len(sizes) + 1


def test_seeded_invalid_options_are_bounded(tmp_path: Path) -> None:
    rng = random.Random(912)
    for _ in range(1000):
        value = "!" + "".join(chr(rng.randrange(0x110000)) for _ in range(rng.randrange(200)))
        with pytest.raises(ValueError) as caught:
            largest(tmp_path, by=value)  # type: ignore[call-overload]
        assert len(str(caught.value)) < 120


def test_deep_tree_does_not_use_python_recursion(tmp_path: Path) -> None:
    import sys

    if os.name == "nt":
        tmp_path = Path("\\\\?\\" + str(tmp_path))
    path = tmp_path
    for _ in range(100):
        path /= "d"
        path.mkdir()
    (path / "f").write_bytes(b"abc")
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(80)
        assert scan(tmp_path).apparent_bytes == 3
        assert len(list(iter_dirs(tmp_path))) == 101
    finally:
        sys.setrecursionlimit(previous)
