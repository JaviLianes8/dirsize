from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import hardlink, symlink, write

from dirsize import scan
from dirsize._cli import main


def _tree(root: Path) -> None:
    write(root / "a.bin", b"a" * 1000)
    write(root / "sub" / "b.bin", b"b" * 3000)


def _run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(list(argv), out=out)
    return code, out.getvalue()


def _lines(text: str) -> list[tuple[str, str]]:
    return [tuple(line.split("\t", 1)) for line in text.splitlines()]  # type: ignore[misc]


def test_default_lists_every_directory_children_first(tmp_path: Path) -> None:
    _tree(tmp_path)
    code, out = _run("-A", str(tmp_path))
    assert code == 0
    rows = _lines(out)
    assert [path for _, path in rows] == [str(tmp_path / "sub"), str(tmp_path)]
    expected = scan(tmp_path, include_dirs=True).apparent_bytes
    assert rows[-1][0] == str(expected)


def test_summarize_prints_one_disk_total_per_path(tmp_path: Path) -> None:
    _tree(tmp_path / "one")
    _tree(tmp_path / "two")
    code, out = _run("-s", str(tmp_path / "one"), str(tmp_path / "two"))
    assert code == 0
    sizes = [int(size) for size, _ in _lines(out)]
    assert sizes == [
        scan(tmp_path / "one", include_dirs=True).disk_bytes,
        scan(tmp_path / "two", include_dirs=True).disk_bytes,
    ]


def test_hard_link_shared_by_two_paths_counts_once(tmp_path: Path) -> None:
    original = write(tmp_path / "a" / "f.bin", b"f" * 9000)
    (tmp_path / "b").mkdir()
    hardlink(tmp_path / "b" / "g.bin", original)
    _, out = _run("-s", "-A", str(tmp_path / "a"), str(tmp_path / "b"))
    assert [size for size, _ in _lines(out)] == ["9000", "0"]
    _, counted = _run("-s", "-A", "-l", str(tmp_path / "a"), str(tmp_path / "b"))
    assert [size for size, _ in _lines(counted)] == ["9000", "9000"]


def test_a_path_given_twice_is_printed_once(tmp_path: Path) -> None:
    _tree(tmp_path)
    _, out = _run("-s", str(tmp_path), str(tmp_path))
    assert len(_lines(out)) == 1


def test_dereference_flag_follows_links(tmp_path: Path) -> None:
    write(tmp_path / "data" / "f.bin", b"d" * 500)
    symlink(tmp_path / "view" / "link", tmp_path / "data")
    _, plain = _run("-s", "-A", str(tmp_path / "view"))
    _, followed = _run("-s", "-A", "-L", str(tmp_path / "view"))
    assert int(followed.split("	")[0]) == 500
    assert int(plain.split("	")[0]) < 500


def test_one_file_system_flag_skips_other_devices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree(tmp_path)
    mounted = os.fspath(tmp_path / "sub")
    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = True) -> os.stat_result:
        info = real_stat(path, follow_symlinks=follow_symlinks)
        if os.fspath(path) == mounted:
            fields = list(info)
            fields[2] = info.st_dev + 1
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(os, "stat", fake_stat)
    _, out = _run("-s", "-A", "-x", str(tmp_path))
    assert out.split("	")[0] == "1000"


def test_unreadable_root_still_prints_a_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = os.fspath(tmp_path)
    real_scandir = os.scandir

    def guarded(path: str) -> object:
        if os.fspath(path) == root:
            raise PermissionError(13, "denied", root)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded)
    code, out = _run(root)
    assert code == 1 and [path for _, path in _lines(out)] == [root]


def test_output_modes_are_exclusive(tmp_path: Path) -> None:
    for pair in (["-s", "--json"], ["-s", "--top", "1"], ["--json", "--top", "1"]):
        with pytest.raises(SystemExit) as exit_info:
            main([*pair, str(tmp_path)])
        assert exit_info.value.code == 2


def test_human_readable_sizes(tmp_path: Path) -> None:
    write(tmp_path / "f.bin", b"x" * 3000)
    _, out = _run("-s", "-A", "-h", str(tmp_path / "f.bin"))
    assert out.split("\t")[0] == "3.0K"


def test_top_lists_the_largest_files(tmp_path: Path) -> None:
    _tree(tmp_path)
    _, out = _run("--top", "1", "-A", str(tmp_path))
    assert _lines(out) == [("3000", str(tmp_path / "sub" / "b.bin"))]


def test_json_document(tmp_path: Path) -> None:
    _tree(tmp_path)
    code, out = _run("--json", str(tmp_path))
    document = json.loads(out)
    assert code == 0 and document["version"] == 1
    (entry,) = document["paths"]
    assert entry["path"] == str(tmp_path) and entry["files"] == 2 and entry["errors"] == []
    assert entry["apparent_bytes"] == scan(tmp_path, include_dirs=True).apparent_bytes


def test_errors_go_to_stderr_and_exit_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _tree(tmp_path)
    missing = tmp_path / "missing"
    code, out = _run("-s", str(tmp_path), str(missing))
    assert code == 1
    assert [path for _, path in _lines(out)] == [str(tmp_path)]
    assert capsys.readouterr().err.startswith(f"dirsize: {missing}: ")


def test_listing_errors_also_exit_one(tmp_path: Path) -> None:
    assert _run(str(tmp_path / "missing"))[0] == 1
    assert _run("--top", "3", str(tmp_path / "missing"))[0] == 1


def test_negative_top_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--top", "-1", str(tmp_path)])
    assert exit_info.value.code == 2


def test_defaults_to_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path / "f.bin", b"x" * 10)
    monkeypatch.chdir(tmp_path)
    _, out = _run("-s", "-A")
    assert _lines(out)[0][1] == "."


def test_module_entry_point_runs(tmp_path: Path) -> None:
    write(tmp_path / "f.bin", b"x" * 10)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    done = subprocess.run(
        [sys.executable, "-m", "dirsize", "-s", "-A", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.returncode == 0 and done.stdout.startswith("10\t")
