from __future__ import annotations

from pathlib import Path

import pytest
from helpers import write

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
    for name in ("x", "y", "z"):
        write(tmp_path / name, b"t" * 10)
    order = [Path(i.path).name for i in largest(tmp_path, 3, by="apparent")]
    walked = [Path(i.path).name for i in largest(tmp_path, 3, by="apparent")]
    assert order == walked and len(order) == 3


def test_largest_by_disk_is_the_default(tmp_path: Path) -> None:
    _tree(tmp_path)
    (first,) = largest(tmp_path, 1)
    assert first.disk_bytes == max(i.disk_bytes for i in largest(tmp_path, 10))


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
