"""The ``dirsize`` command: ``du``-style lines or JSON for one or more paths."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import TextIO

from ._core import iter_dirs, largest, scan
from ._types import DirUsage, FileUsage, Measure, ScanError, Usage

_UNITS = ("B", "K", "M", "G", "T", "P", "E")


def human(size: int) -> str:
    """Format ``size`` with binary units the way ``du -h`` does: one decimal below 10."""
    value = float(size)
    for unit in _UNITS:
        if value < 1024 or unit == _UNITS[-1]:
            if unit == "B":
                return f"{size}B"
            text = f"{value:.1f}" if value < 10 else f"{value:.0f}"
            return f"{text}{unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="dirsize",
        add_help=False,
        description="Report the space used by directory trees, like du.",
    )
    add = parser.add_argument
    add("paths", nargs="*", default=["."], metavar="PATH", help="paths to measure")
    add("--help", action="help", help="show this message and exit")
    add("--version", action="version", version=f"dirsize {__version__}")
    add("-s", "--summarize", action="store_true", help="print only one total per path")
    add("-A", "--apparent-size", action="store_true", help="use st_size instead of disk usage")
    add("-h", "--human-readable", action="store_true", help="print sizes like 1.5K, 20M")
    add("-x", "--one-file-system", action="store_true", help="skip other file systems")
    add("-L", "--dereference", action="store_true", help="follow symlinks and junctions")
    add("-l", "--count-links", action="store_true", help="count hard-linked files every time")
    add("--top", type=int, metavar="N", help="list the N largest files instead")
    add("--json", action="store_true", help="print one JSON document")
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    """Run the command line and return its exit status: 0, or 1 if any path had errors."""
    args = _parser().parse_args(argv)
    if args.top is not None and args.top < 0:
        _parser().error("--top must be zero or more")
    stdout = out or sys.stdout
    by: Measure = "apparent" if args.apparent_size else "disk"
    show = human if args.human_readable else str
    options = {
        "follow_symlinks": args.dereference,
        "one_filesystem": args.one_file_system,
    }
    errors: list[ScanError] = []
    documents: list[dict[str, object]] = []

    def collect(error: OSError) -> None:
        errors.append(ScanError.from_os_error(error))

    for path in args.paths:
        if args.json or args.summarize:
            usage = scan(path, count_links=args.count_links, include_dirs=True, **options)
            errors.extend(usage.errors)
            if args.json:
                documents.append(asdict(usage))
            elif usage.measured:
                print(f"{show(_pick(usage, by))}	{path}", file=stdout)
        elif args.top is not None:
            for item in largest(path, args.top, by=by, on_error=collect, **options):
                print(f"{show(_pick(item, by))}	{item.path}", file=stdout)
        else:
            for item in iter_dirs(
                path, count_links=args.count_links, include_dirs=True, on_error=collect, **options
            ):
                print(f"{show(item.size(by))}	{item.path}", file=stdout)
    if args.json:
        json.dump({"version": 1, "paths": documents}, stdout, indent=2)
        stdout.write("\n")
    for error in errors:
        print(f"dirsize: {error.path}: {error.message}", file=sys.stderr)
    return 1 if errors else 0


def _pick(item: FileUsage | DirUsage | Usage, by: Measure) -> int:
    return item.disk_bytes if by == "disk" else item.apparent_bytes
