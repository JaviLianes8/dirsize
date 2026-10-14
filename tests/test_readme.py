"""Run every Python example in the README against a generated ``my_project`` tree."""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest
from helpers import write

README = Path(__file__).resolve().parents[1] / "README.md"
BLOCKS = re.findall(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.S)


def test_the_readme_has_examples() -> None:
    assert len(BLOCKS) >= 5


@pytest.mark.parametrize("code", BLOCKS)
def test_readme_example_runs(code: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path / "my_project" / "a.bin", b"a" * 100)
    write(tmp_path / "my_project" / "src" / "b.bin", b"b" * 50)
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "README.md", "exec"), {})
    assert out.getvalue() or "scan(" in code
