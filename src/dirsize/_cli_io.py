"""Command line plumbing: bounded usage errors, any file name printable, quiet closed pipes."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, NoReturn, TextIO

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

# Usage error messages are cut here, so a huge argument is never echoed back whole.
MESSAGE_LIMIT = 300


class LostOutput(Exception):
    """The reader of a stream went away (a closed pipe or a closed file)."""


def emit(stream: TextIO, text: str, *, flush: bool = False) -> None:
    """Write ``text``; raise :class:`LostOutput` when the stream's reader is gone.

    A name the stream cannot encode is written as its raw bytes when it came from
    undecodable bytes (as ``du`` prints it), else with backslash escapes.
    """
    try:
        try:
            stream.write(text)
        except UnicodeEncodeError:
            _write_escaped(stream, text)
        if flush:
            stream.flush()
    except (OSError, ValueError) as error:
        silence(stream)
        raise LostOutput from error


def _write_escaped(stream: TextIO, text: str) -> None:
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        stream.write(text.encode("ascii", "backslashreplace").decode("ascii"))
        return
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        data = text.encode(encoding, "surrogateescape")
    except UnicodeEncodeError:
        data = text.encode(encoding, "backslashreplace")
    stream.flush()
    buffer.write(data)


def silence(stream: object) -> None:
    """Point ``stream``'s descriptor at the null device after its reader went away.

    Python flushes the streams at exit; on a closed pipe that flush fails and the
    process exits 120 with a warning. Redirecting the descriptor makes every later
    write succeed. Only the failing stream is touched.
    """
    try:
        fd = stream.fileno()  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return
    null = os.open(os.devnull, os.O_WRONLY)
    if null != fd:  # a closed fd is reused by open(): then it already is the null device
        os.dup2(null, fd)
        os.close(null)


def say(text: str) -> None:
    """Write ``text`` to standard error; a lost standard error is ignored."""
    try:
        emit(sys.stderr, text, flush=True)
    except LostOutput:
        return


def finish(code: int) -> int:
    """Flush both standard streams and return ``code``; a lost stream is silenced."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError):
            silence(stream)
    return code


class Parser(argparse.ArgumentParser):
    """An argument parser whose errors are bounded and survive a closed stream."""

    def error(self, message: str) -> NoReturn:
        if len(message) > MESSAGE_LIMIT:
            message = message[:MESSAGE_LIMIT] + "..."
        self.exit(2, f"{self.format_usage()}{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            say(message)
        raise SystemExit(finish(status))

    def _print_message(self, message: str, file: SupportsWrite[str] | None = None) -> None:
        if not message:
            return
        if file is sys.stderr:
            say(message)
            return
        try:
            emit(sys.stdout, message, flush=True)
        except LostOutput:
            return
