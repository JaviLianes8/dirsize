from __future__ import annotations

import os
from pathlib import Path

import pytest
from helpers import hardlink, sparse, write

from dirsize import DirUsage, FileUsage, iter_dirs, largest


def _tree(root: Path) -> None:
    write(root / "big.bin", b"b" * 300)
    write(root / "a" / "one.bin", b"1" * 100)
    write(root / "a" / "deep" / "two.bin", b"2" * 200)
    write(root / "c" / "three.bin", b"3" * 50)


def test_directories_stream_children_first_root_last(tmp_path: Path) -> None:
    _tree(tmp_path)
    dirs = list(iter_dirs(tmp_path))
    names = [Path(d.path).name for d in dirs]
    assert names.index("deep") < names.index("a")
    assert names[-1] == tmp_path.name and dirs[-1].depth == 0
    assert {Path(d.path).name: d.depth for d in dirs}["deep"] == 2


def test_each_directory_total_includes_its_subtree(tmp_path: Path) -> None:
    _tree(tmp_path)
    by_name = {Path(d.path).name: d for d in iter_dirs(tmp_path)}
    assert by_name["deep"].apparent_bytes == 200
    assert (by_name["a"].apparent_bytes, by_name["a"].files, by_name["a"].dirs) == (300, 2, 1)
    root = by_name[tmp_path.name]
    assert (root.apparent_bytes, root.files, root.dirs) == (650, 4, 3)


def test_iter_dirs_is_lazy_and_validates_eagerly(tmp_path: Path) -> None:
    _tree(tmp_path)
    stream = iter_dirs(tmp_path)
    assert isinstance(next(stream), DirUsage)
    with pytest.raises(ValueError):
        iter_dirs(tmp_path, on_error="nope")  # type: ignore[arg-type]


def test_size_picks_the_measure() -> None:
    usage = DirUsage("p", 3, 4096, 1, 0, 0, 0, 0)
    assert (usage.size(), usage.size("disk"), usage.size("apparent")) == (4096, 4096, 3)


def test_largest_files_biggest_first(tmp_path: Path) -> None:
    _tree(tmp_path)
    top = largest(tmp_path, 2, by="apparent")
    assert all(isinstance(item, FileUsage) for item in top)
    assert [Path(item.path).name for item in top] == ["big.bin", "two.bin"]


def test_largest_directories(tmp_path: Path) -> None:
    _tree(tmp_path)
    top = largest(tmp_path, 3, by="apparent", kind="dir")
    assert [Path(item.path).name for item in top] == [tmp_path.name, "a", "deep"]


def test_largest_ties_keep_walk_order(tmp_path: Path) -> None:
    for name in ("x", "y", "z", "w"):
        write(tmp_path / name, b"t" * 10)
    walked = [entry.name for entry in os.scandir(tmp_path)]
    assert [Path(i.path).name for i in largest(tmp_path, 4, by="apparent")] == walked
    assert [Path(i.path).name for i in largest(tmp_path, 2, by="apparent")] == walked[:2]


def test_largest_by_disk_differs_from_by_apparent(tmp_path: Path) -> None:
    write(tmp_path / "dense.bin", os.urandom(200_000))
    sparse(tmp_path / "hole.bin", 10 << 20)
    (by_disk,) = largest(tmp_path, 1)
    (by_size,) = largest(tmp_path, 1, by="apparent")
    assert Path(by_disk.path).name == "dense.bin"
    assert Path(by_size.path).name == "hole.bin"
    (biggest_dir,) = largest(tmp_path, 1, kind="dir", by="apparent")
    assert biggest_dir.apparent_bytes == 200_000 + (10 << 20)


def test_largest_count_links_weighs_every_name(tmp_path: Path) -> None:
    original = write(tmp_path / "a.bin", b"a" * 300)
    hardlink(tmp_path / "b.bin", original)
    plain = sorted(i.apparent_bytes for i in largest(tmp_path, 2, by="apparent"))
    counted = largest(tmp_path, 2, by="apparent", count_links=True)
    assert plain == [0, 300]
    assert [i.apparent_bytes for i in counted] == [300, 300]


def test_largest_zero_and_more_than_available(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert largest(tmp_path, 0) == []
    assert len(largest(tmp_path, 99)) == 4


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({"n": -1}, "n must"), ({"by": "size"}, "by must"), ({"kind": "link"}, "kind must")],
)
def test_largest_rejects_bad_arguments(
    tmp_path: Path, kwargs: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        largest(tmp_path, **kwargs)  # type: ignore[arg-type]
