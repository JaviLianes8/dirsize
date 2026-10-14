"""Build the wheel, install it in a throwaway venv and drive the installed command.

Slow and needs the build backend, so it runs only with DIRSIZE_E2E=1.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("DIRSIZE_E2E") != "1", reason="set DIRSIZE_E2E=1 to build and install"
)


def _run(*cmd: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=False)


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("dirsize-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    assert _run(python, "-m", "pip", "install", "-q", wheel).returncode == 0
    script = bindir / ("dirsize.exe" if sys.platform == "win32" else "dirsize")

    tree = tmp_path / "tree"
    (tree / "sub").mkdir(parents=True)
    (tree / "a.bin").write_bytes(b"a" * 1000)
    (tree / "sub" / "b.bin").write_bytes(b"b" * 3000)

    version = _run(script, "--version")
    assert version.returncode == 0 and version.stdout.startswith("dirsize 0.")

    summary = _run(script, "-s", "-A", tree)
    assert summary.returncode == 0 and summary.stdout == f"4000\t{tree}\n"

    listing = _run(script, "-A", tree)
    assert [line.split("\t")[1] for line in listing.stdout.splitlines()] == [
        str(tree / "sub"),
        str(tree),
    ]

    top = _run(script, "--top", "1", "-A", "-h", tree)
    assert top.stdout == f"3.0K\t{tree / 'sub' / 'b.bin'}\n"

    report = json.loads(_run(script, "--json", tree).stdout)
    assert report["paths"][0]["files"] == 2 and report["paths"][0]["apparent_bytes"] == 4000

    bad = _run(script, "-s", tree / "missing")
    assert bad.returncode == 1 and bad.stderr.startswith("dirsize: ") and bad.stdout == ""

    api = _run(
        python,
        "-c",
        "import dirsize, importlib.resources as r; "
        f"u = dirsize.scan({str(tree)!r}); "
        "print(u.apparent_bytes, u.files, r.files('dirsize').joinpath('py.typed').is_file())",
    )
    assert api.stdout.split() == ["4000", "2", "True"]
