"""The ``dirsize`` command: ``du``-style lines or JSON for one or more paths."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import TextIO

from ._core import largest, measure
from ._types import DirUsage, FileUsage, Measure, ScanError, Usage, WalkOptions
from ._walk import Seen, walk

_UNITS = ("B", "K", "M", "G", "T", "P", "E")


def human(size: int) -> str:
    """Format ``size`` like ``du -h``: binary units, rounded up, one decimal below 10."""
    if size < 1024:
        return str(size)
    value = size / 1024
    for unit in _UNITS[1:]:
        tenths = math.ceil(value * 10)
        if tenths < 100:
            return f"{tenths / 10:.1f}{unit}"
        whole = math.ceil(value)
        if whole < 1024 or unit == _UNITS[-1]:
            return f"{whole}{unit}"
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
    add("-A", "--apparent-size", action="store_true", help="use st_size instead of disk usage")
    add("-h", "--human-readable", action="store_true", help="print sizes like 1.5K, 20M")
    add("-x", "--one-file-system", action="store_true", help="skip other file systems")
    add("-L", "--dereference", action="store_true", help="follow symlinks and junctions")
    add("-l", "--count-links", action="store_true", help="count hard-linked files every time")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-s", "--summarize", action="store_true", help="one total per path")
    mode.add_argument("--top", type=int, metavar="N", help="list the N largest files instead")
    mode.add_argument("--json", action="store_true", help="print one JSON document")
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    """Run the command line and return its exit status: 0, or 1 if any path had errors."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.top is not None and args.top < 0:
        parser.error("--top must be zero or more")
    stdout = out or sys.stdout
    by: Measure = "apparent" if args.apparent_size else "disk"
    show = human if args.human_readable else str
    options = WalkOptions(args.dereference, args.one_file_system, args.count_links, True)
    errors: list[ScanError] = []
    documents: list[dict[str, object]] = []
    seen = Seen()  # one hard link or directory counts once across all paths, as in du

    def collect(error: OSError) -> None:
        errors.append(ScanError.from_os_error(error))

    for path in args.paths:
        if args.json or args.summarize:
            usage = measure(path, options, collect, seen)
            if args.json:
                documents.append(asdict(usage))
            elif usage.measured:
                print(f"{show(_pick(usage, by))}\t{path}", file=stdout)
        elif args.top is not None:
            found = largest(
                path,
                args.top,
                by=by,
                follow_symlinks=args.dereference,
                one_filesystem=args.one_file_system,
                count_links=args.count_links,
                on_error=collect,
            )
            for item in found:
                print(f"{show(_pick(item, by))}\t{item.path}", file=stdout)
        else:
            for item in walk(os.fspath(path), options, collect, seen):
                if isinstance(item, DirUsage):
                    print(f"{show(item.size(by))}\t{item.path}", file=stdout)
    if args.json:
        json.dump({"version": 1, "paths": documents}, stdout, indent=2)
        stdout.write("\n")
    for error in errors:
        print(f"dirsize: {error.path}: {error.message}", file=sys.stderr)
    return 1 if errors else 0


def _pick(item: FileUsage | DirUsage | Usage, by: Measure) -> int:
    return item.disk_bytes if by == "disk" else item.apparent_bytes
