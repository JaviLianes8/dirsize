"""The ``dirsize`` command: ``du``-style lines or JSON for one or more paths."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import TextIO

from ._cli_io import LostOutput, Parser, emit, finish, say
from ._core import measure
from ._errors import ScanError
from ._human import human
from ._largest import top_items
from ._results import DirUsage
from ._state import Seen
from ._types import Measure, WalkOptions
from ._walk import walk


def _parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = Parser(
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
    """Run the command line and return its exit status: 0, or 1 if anything failed.

    Errors go to standard error as they happen. A closed output pipe ends the run
    quietly with status 1.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    if args.top is not None and args.top < 0:
        parser.error("--top must be zero or more")
    failures = 0

    def report(error: OSError) -> None:
        nonlocal failures
        failures += 1
        found = ScanError.from_os_error(error)
        say(f"dirsize: {found.path}: {found.message}\n")

    stdout = out or sys.stdout
    try:
        _run(args, stdout, report)
        emit(stdout, "", flush=True)
    except LostOutput:
        return finish(1)
    return finish(1 if failures else 0)


def _run(args: argparse.Namespace, stdout: TextIO, report: Callable[[OSError], None]) -> None:
    by: Measure = "apparent" if args.apparent_size else "disk"
    show = human if args.human_readable else str
    options = WalkOptions(args.dereference, args.one_file_system, args.count_links, True)
    documents: list[dict[str, object]] = []
    seen = Seen()  # one hard link or directory counts once across all paths, as in du
    for path in args.paths:
        if args.json or args.summarize:
            usage = measure(path, options, report, seen)
            if args.json:
                documents.append(asdict(usage))
            elif usage.measured:
                emit(stdout, f"{show(usage.size(by))}\t{path}\n")
        elif args.top is not None:
            items = walk(path, options, report, seen)
            for item in top_items(items, args.top, by, "file"):
                emit(stdout, f"{show(item.size(by))}\t{item.path}\n")
        else:
            for item in walk(path, options, report, seen):
                if isinstance(item, DirUsage):
                    emit(stdout, f"{show(item.size(by))}\t{item.path}\n")
    if args.json:
        emit(stdout, json.dumps({"version": 1, "paths": documents}, indent=2) + "\n")
