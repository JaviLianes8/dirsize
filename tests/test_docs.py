"""Every example in the docstrings, the README and the GUIDE runs and prints what it says."""

from __future__ import annotations

import contextlib
import doctest
import importlib
import io
import re
import tempfile
from pathlib import Path

import pytest

import dirsize

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
GUIDE = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
BADGE = (
    "[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)]"
    "(https://lianes8studio.com/certified)"
)
MODULES = [
    "dirsize",
    *(f"dirsize.{p.stem}" for p in sorted((ROOT / "src" / "dirsize").glob("_*.py"))),
]
PUBLIC_CLASSES = [dirsize.DirUsage, dirsize.FileUsage, dirsize.ScanError, dirsize.Usage]


def build_project(base: Path) -> Path:
    """The ``my_project`` folder the README and GUIDE describe."""
    root = base / "my_project"
    for name, size in [
        ("README.txt", 1000),
        ("logo.png", 20_000),
        ("src/app.py", 3000),
        ("src/lib/util.py", 150),
    ]:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(b"x" * size)
    return root


def _blocks(text: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def _expected(block: str) -> list[str]:
    # Every comment in an example is output: after a print call, or on a line of its own.
    return re.findall(r"^(?:\s*print\(.*\)  |)# (.+)$", block, flags=re.MULTILINE)


def _doctests() -> list[doctest.DocTest]:
    finder = doctest.DocTestFinder()
    found = [t for name in MODULES for t in finder.find(importlib.import_module(name))]
    # The classes name the package as their module, so their methods are found from here.
    for cls in PUBLIC_CLASSES:
        found += finder.find(cls, cls.__name__, module=False, globs=vars(dirsize).copy())
    return [test for test in found if test.examples]


@pytest.mark.parametrize(("name", "count"), [("README", 3), ("GUIDE", 5)])
def test_every_doc_example_prints_what_its_comments_say(
    name: str, count: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocks = _blocks(README if name == "README" else GUIDE)
    assert len(blocks) == count
    for index, block in enumerate(blocks):
        base = tmp_path / str(index)
        build_project(base)
        monkeypatch.chdir(base)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(block, f"{name}.md", "exec"), {"__name__": name.lower()})
        assert _expected(block), block
        assert out.getvalue().splitlines() == _expected(block), block


def test_every_docstring_example_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    tests = _doctests()
    for test in tests:
        runner.run(test)
    results = runner.summarize(verbose=False)
    assert results.failed == 0
    assert results.attempted >= 40 and len(tests) >= 20


def test_every_public_name_and_method_has_an_example() -> None:
    names = {test.name.rsplit(".", 1)[-1] for test in _doctests()}
    for name in dirsize.__all__:
        obj = getattr(dirsize, name)
        if callable(obj) and not hasattr(obj, "__origin__"):
            assert name in names, name
    for cls in PUBLIC_CLASSES:
        methods = [m for m in vars(cls) if not m.startswith("_") and m not in cls.__match_args__]
        for method in methods:
            assert f"{cls.__name__}.{method}" in {t.name for t in _doctests()}, method
    # The aliases are shown in the package docstring.
    for alias in ("ErrorKind", "Measure", "OnError"):
        assert alias in (dirsize.__doc__ or "")


def test_the_readme_has_the_badge_and_absolute_links() -> None:
    assert README.splitlines()[2] == BADGE
    for target in re.findall(r"\]\(([^)]+)\)", README):
        assert target.startswith("https://"), target
    assert "GUIDE.md" in README and "CHANGELOG.md" in README


def test_the_api_table_names_every_public_name() -> None:
    table = README.split("## API", 1)[1].split("\n## ", 1)[0]
    for name in dirsize.__all__:
        assert f"`{name}" in table, name


def test_version_pyproject_and_changelog_agree() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'\nversion = "{dirsize.__version__}"\n' in pyproject
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(
        rf"^## \[{re.escape(dirsize.__version__)}\] - \d{{4}}-\d\d-\d\d$", changelog, re.M
    )


def test_text_files_have_no_em_dash_or_nul() -> None:
    suffixes = {".py", ".md", ".toml", ".ps1", ".txt", ".json", ".yml", ".cfg"}
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if any(
            p.startswith(".") or p in ("__pycache__", "build", "dist", "upstream") for p in parts
        ):
            continue
        data = path.read_bytes()
        assert chr(0x2014).encode() not in data and b"\x00" not in data, path


def test_source_files_stay_under_two_hundred_lines() -> None:
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").glob("*.py")]:
        assert path.read_text(encoding="utf-8").count("\n") <= 200, path
