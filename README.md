# dirsize

[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)](https://lianes8studio.com/certified)

The size of a directory tree, apparent and on disk, as typed calls and a `du`-like
command. Hard links count once, symlinks and Windows junctions are never followed by
surprise, and unreadable folders are reported next to the result instead of ending the
scan.

## The problem

Python has no call for "how big is this folder". `shutil.disk_usage` answers for the
whole file system that holds a path, not for a tree. The usual recipe, `os.path.getsize`
summed over `os.walk`, gets several things wrong:

- a file with several hard links is added once per name;
- it adds `st_size`, not the space the file takes, so sparse and compressed files count
  at their full length;
- on Windows, `os.walk` enters directory junctions by default. A junction that points at a
  parent folder revisits the same contents;
- with `followlinks=True` it can loop on symlinks too, as the `os.walk` documentation warns.

GNU `du` gets these right, but it is a separate program whose output you have to parse,
and it is not bundled with Windows. `dirsize` gives you similar rules as typed functions, on
Linux and Windows, with no dependencies.

## Install

```
pip install dirsize
```

Python 3.10 or newer.

## Quick start

The examples below measure a folder `my_project` that holds `README.txt` (1,000
bytes), `logo.png` (20,000 bytes), `src/app.py` (3,000 bytes) and `src/lib/util.py`
(150 bytes).

```python
from dirsize import scan

usage = scan("my_project")
print(usage.apparent_bytes, usage.files, usage.dirs, usage.ok)  # 24150 4 2 True
print(usage.disk_bytes >= 20000)  # True
```

`apparent_bytes` is the sum of the file sizes, what `ls -l` shows. `disk_bytes` is the
space the files take on the disk, which is larger for small files (space comes in
blocks) and smaller for sparse or compressed ones. By default, filesystem errors do not
stop a scan: each one is kept in `usage.errors` as a `ScanError` with the path, a kind
and the system message.

```python
from pathlib import Path

from dirsize import iter_dirs, largest

for folder in iter_dirs("my_project"):
    print(Path(folder.path).name, folder.apparent_bytes, folder.depth)
# lib 150 2
# src 3150 1
# my_project 24150 0

for item in largest("my_project", 2, by="apparent"):
    print(Path(item.path).name, item.apparent_bytes)
# logo.png 20000
# app.py 3000
```

`iter_dirs` streams one total per folder, children before their parent and the root
last, like `du` without `-s`; sibling folders come in the order the file system lists
them. `largest` keeps only `n` items in memory while it walks.

```python
from dirsize import dir_size, file_count

print(dir_size("my_project"), file_count("my_project"))  # 24150 4
```

## Command line

```
dirsize [-s] [-A] [-h] [-x] [-L] [-l] [--top N] [--json] [PATH ...]
```

Without options it prints the disk usage in bytes of every directory, children first,
like `du`. `-s` prints one total per path, `-A` uses apparent sizes and `-h` prints sizes
such as `1.5K` or `20M`, rounded up exactly as `du -h` does. `--top N` lists the N largest
files of each path and `--json` prints one document with the totals and errors of each
path; `-s`, `--top` and `--json` exclude each other. `-x`, `-L` and `-l` mean what they
mean for `du`. Errors go to standard error and make the exit status 1. The same tool
runs as `python -m dirsize`.

## API

| Name | What it is |
| --- | --- |
| `scan(path, ...)` | totals of a tree and every error met, as a `Usage` |
| `iter_dirs(path, ...)` | a `DirUsage` per directory, streamed, root last |
| `largest(path, n=10, ...)` | the `n` biggest files (`FileUsage`) or folders (`DirUsage`) |
| `dir_size(path, ...)` | apparent bytes of every file, hard links once |
| `file_count(path, ...)` | number of non-directory entries |
| `Usage`, `DirUsage`, `FileUsage` | frozen results with `apparent_bytes`, `disk_bytes` and `size(by)` |
| `ScanError` | one path that could not be measured: `path`, `kind`, `message` |
| `Measure`, `ErrorKind`, `OnError` | the accepted values of `by`, `kind` and `on_error` |

Options: `follow_symlinks`, `one_filesystem` (`du -x`), `count_links` (`du -l`),
`include_dirs` (count the blocks of the folders themselves, as `du` does) and
`on_error` (`"ignore"`, `"raise"` or a callable). The
[guide](https://github.com/JaviLianes8/dirsize/blob/main/GUIDE.md) has the exact
counting rules, the platform details, the errors, the command line and its JSON
document; the
[changelog](https://github.com/JaviLianes8/dirsize/blob/main/CHANGELOG.md) lists every
change.

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/dirsize/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
