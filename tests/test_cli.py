from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import write

from dirsize import scan
from dirsize._cli import human, main


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
    _tree(tmp_path)
    code, out = _run("-s", str(tmp_path), str(tmp_path / "sub"))
    assert code == 0
    sizes = [int(size) for size, _ in _lines(out)]
    assert sizes == [
        scan(tmp_path, include_dirs=True).disk_bytes,
        scan(tmp_path / "sub", include_dirs=True).disk_bytes,
    ]


def test_human_readable_sizes(tmp_path: Path) -> None:
    write(tmp_path / "f.bin", b"x" * 3000)
    _, out = _run("-s", "-A", "-h", str(tmp_path / "f.bin"))
    assert out.split("\t")[0] == "3.0K"


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0B"),
        (1023, "1023B"),
        (1024, "1.0K"),
        (1025, "1.1K"),
        (10 * 1024 - 1, "10K"),
        (10 * 1024, "10K"),
        (1024 * 1024 - 1, "1.0M"),
        (1536 * 1024, "1.5M"),
    ],
)
def test_human_format(size: int, text: str) -> None:
    assert human(size) == text


def test_human_caps_at_the_largest_unit() -> None:
    assert human(1 << 70).endswith("E")


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


def test_count_links_and_one_file_system_flags_are_accepted(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert _run("-s", "-l", "-x", "-L", str(tmp_path))[0] == 0


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
