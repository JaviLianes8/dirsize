# dirsize guide

Everything `dirsize` promises, in detail. The examples run against the same
`my_project` folder as the README: `README.txt` (1,000 bytes), `logo.png` (20,000
bytes), `src/app.py` (3,000 bytes) and `src/lib/util.py` (150 bytes). Each example
starts from a fresh copy of it.

## What is counted

- **Apparent size** (`apparent_bytes`) is the sum of `st_size` over regular files and
  symlinks, as GNU `du --apparent-size` counts it. Directories, devices, pipes and
  sockets add 0.
- **Disk usage** (`disk_bytes`) is the space allocated. On Linux and macOS it is
  `st_blocks * 512`. On Windows it is the `AllocationSize` NTFS reports for the file
  (`GetFileInformationByHandleEx` with `FileStandardInfo`), which accounts for
  compression, sparse ranges and tiny files stored inside the file table; links and
  folders take 0 there, and a file that cannot be opened counts its plain size.
- **Files** (`files`) counts every non-directory entry once per name: regular files,
  links left unfollowed, devices, pipes and sockets.
- **Hard links.** A file with several names adds its bytes once, under the first name
  met, unless `count_links=True` (`du -l`). Every name still counts in `files`.
- **Links.** A symlink below the root, or on Windows a junction or any other reparse
  point that names another path (its tag has the name surrogate bit), counts as a file
  entry of its own size and is not entered; `links` counts these entries. With
  `follow_symlinks=True` its target is measured instead and a file reached through
  several links counts once, as with `du -L`. The root path is always resolved, like
  `du -D`.
- **Directories** (`dirs`) counts the directories entered below the root, and those
  that could not be read. A directory is entered at most once per device and file id:
  a second way into it is skipped silently and not counted.
- **Cycles.** A followed link back to a parent folder is skipped silently, as `du -L`
  does. A physical loop (a bind mount of a parent, a hard-linked directory) is a
  `cycle` error, as `du` warns about a circular directory structure.
- **`include_dirs=True`** adds the blocks each directory takes, as `du` does; with it,
  the totals match GNU `du -sb` (apparent) and `du -sB1` (disk) on Linux.
- **`one_filesystem=True`** skips directories on another device than the root
  (`du -x`).

```python
import os

from dirsize import scan

os.link("my_project/logo.png", "my_project/logo-copy.png")
usage = scan("my_project")
print(usage.apparent_bytes, usage.files)  # 24150 5
print(scan("my_project", count_links=True).apparent_bytes)  # 44150
```

## Results

All results are frozen dataclasses; `size(by)` returns `disk_bytes` for `"disk"` (the
default) and `apparent_bytes` for `"apparent"`, and raises `ValueError` for anything
else.

- `Usage` (from `scan`): `path`, `apparent_bytes`, `disk_bytes`, `files`, `dirs`,
  `links`, `errors` (a tuple of `ScanError`), `measured` (false when `path` itself could
  not be read; the totals are then 0) and the property `ok` (measured with no error).
- `DirUsage` (from `iter_dirs`, `largest(kind="dir")`): the same totals for one
  directory's subtree, plus `errors` as a count and `depth` (0 for the root).
- `FileUsage` (from `largest`): `path`, `apparent_bytes`, `disk_bytes`, `is_link`.
  A second name of a hard-linked file weighs 0 unless `count_links=True`.

Paths in results are the path you passed joined with the names found, as
`os.scandir` builds them. Results pickle by their public names (`dirsize.Usage`).

```python
from dirsize import largest

(top,) = largest("my_project", 1, by="apparent", kind="dir")
print(top.size("apparent"), top.files, top.dirs, top.depth)  # 24150 4 2 0
```

## Errors

Mistakes in the call are raised at once, before anything is read:

| Problem | Raised |
| --- | --- |
| `path` is not a `str` or `os.PathLike[str]` (bytes paths included) | `TypeError` |
| `on_error` is not `"raise"`, `"ignore"` or a callable | `ValueError` |
| `by` is not `"disk"` or `"apparent"`; `kind` is not `"file"` or `"dir"` | `ValueError` |
| `n` is not an `int` (`bool` included) | `TypeError` |
| `n` is negative | `ValueError` |

A path holding a NUL character raises `ValueError` too. Messages quote at most 40
characters of a bad value.

Problems met while reading the tree are `OSError`s, handled by `on_error`:
`"ignore"` (the default of `scan`, `iter_dirs` and `largest`) goes on, `"raise"` (the
default of `dir_size` and `file_count`) raises the first one, and a callable receives
each one and the walk goes on unless it raises. `scan` also keeps every error in
`Usage.errors`, whatever `on_error` is, and each `DirUsage` counts the errors met in
its subtree. Each kept error is a `ScanError` whose `kind` is:

| Kind | When |
| --- | --- |
| `permission` | a folder or file the account may not read |
| `missing` | a path that vanished during the walk, or a dangling link met with `follow_symlinks=True` |
| `cycle` | a physical directory loop, or a chain of links the system refuses to resolve |
| `other` | anything else, a read error for example |

An unreadable directory still counts with its own size and one error, as `du` counts it.

```python
from dirsize import dir_size, scan

usage = scan("my_project/missing")
print(usage.measured, usage.ok, usage.errors[0].kind)  # False False missing
print(dir_size("my_project/missing", on_error="ignore"))  # 0
met = []
print(dir_size("my_project/missing", on_error=met.append), len(met))  # 0 1
try:
    dir_size("my_project/missing")
except FileNotFoundError:
    print("raised")  # raised
```

```python
from dirsize import largest

try:
    largest("my_project", -1)
except ValueError as error:
    print(error)  # n must be zero or more
try:
    largest("my_project", by="size")
except ValueError as error:
    print(error)  # by must be 'disk' or 'apparent', got 'size'
```

## Streaming and memory

`iter_dirs` yields each directory as soon as its subtree is done: children before
their parent, the root last, siblings in the order the file system lists them. It
holds the stack of open directories and the identities of the directories and
hard-linked files seen; closing the iterator early closes every open directory
listing. `largest` holds at most `n` results; ties keep walk order. `scan`,
`dir_size` and `file_count` hold no per-file data.

```python
from pathlib import Path

from dirsize import iter_dirs

walk = iter_dirs("my_project")
first = next(walk)
print(Path(first.path).name, first.depth)  # lib 2
walk.close()
```

## Command line

```
dirsize [-s | --top N | --json] [-A] [-h] [-x] [-L] [-l] [PATH ...]
```

| Option | Meaning |
| --- | --- |
| (none) | one line per directory, children first, disk usage in bytes |
| `-s`, `--summarize` | one total per path |
| `--top N` | the N largest files of each path, biggest first |
| `--json` | one JSON document for all paths |
| `-A`, `--apparent-size` | apparent sizes instead of disk usage |
| `-h`, `--human-readable` | sizes such as `1.5K` or `20M` |
| `-x`, `--one-file-system` | skip directories on other devices |
| `-L`, `--dereference` | follow symlinks and junctions |
| `-l`, `--count-links` | count hard-linked files every time |
| `--version`, `--help` | print and exit |

Lines are `size<TAB>path`, as `du` prints them, with sizes in bytes. Paths default to
`.`. Directories always include their own blocks (as `du` does), so on Linux the output
matches `du -B1`, `du -sB1`, `du -b` and `du -sb` (with `-A`) byte for byte. A hard link or a directory shared by several paths
counts only under the first, and a path given twice prints once, like `du`. Command
line paths are resolved when they are links, like `du -D`.

`-h` follows GNU `du -h` exactly: powers of 1024, the letters `K M G T P E Z Y R Q`,
one decimal below 10, rounded up (`1025` bytes print as `1.1K`), plain bytes below
1024, and a point regardless of the locale.

`--json` prints `{"version": 1, "paths": [...]}`, one entry per path with `path`,
`apparent_bytes`, `disk_bytes`, `files`, `dirs`, `links`, `errors` (a list of
`{"path", "kind", "message"}`) and `measured`. The `-A` and `-h` options do not change
it.

Errors go to standard error as `dirsize: PATH: MESSAGE` while the walk goes on. The
exit status is 0 when everything was read, 1 when anything failed or the reader of
standard output went away (`dirsize | head` ends quietly), and 2 for a usage error. A
file name the output cannot encode is printed as its raw bytes on POSIX, as `du`
does, or with backslash escapes.

## Differences from GNU du

- `dirsize` resolves a command line link (`du -D`); plain `du` measures the link.
- A directory reached a second time is skipped even without `-L` (two bind mounts of
  one folder); `du` counts both unless `-L`.
- Windows junctions and other name surrogate reparse points are links.
- `--top` and `--json` have no `du` counterpart.

## Upgrading from 0.2.0

0.2.0 was never published to PyPI. If you used it from source:

- `largest` now raises `TypeError` for an `n` that is not an `int` (a `bool` included),
  and is typed per `kind` (`list[FileUsage]` or `list[DirUsage]`).
- `DirUsage.size` raises `ValueError` for an unknown `by` instead of returning the
  apparent size; `Usage` and `FileUsage` gained the same `size(by)`.
- `Usage.ok` is false for a path that was not measured.
- Bytes paths raise `TypeError` instead of producing bytes in the results.
- An unreadable subdirectory now yields its own `DirUsage` (one error, its own blocks
  with `include_dirs`) and counts in its parent's `dirs`, as `du` lists it.
- A symlink loop is a `cycle` error on Windows too.
- The command line prints errors as they happen, shares hard links and folders across
  paths in `--top` as in the other modes, prints exact `-h` sizes beyond 2**53 bytes
  and the units after `E`, ends quietly with status 1 when its output pipe closes, and
  prints names its output cannot encode instead of failing.
