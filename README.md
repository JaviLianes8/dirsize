# dirsize

Size of a directory tree, apparent and on disk, as typed calls and a `du`-like
command. Hard links count once, symlinks and Windows junctions are never followed
by surprise, and unreadable folders are reported instead of ending the scan.

## Install

```
pip install dirsize
```

## Usage

```python
from dirsize import scan

usage = scan("my_project")
print(usage.disk_bytes, usage.apparent_bytes, usage.files, usage.dirs)
for error in usage.errors:
    print("skipped:", error.path, error.kind, error.message)
```

`disk_bytes` is the space the files take on the disk. `apparent_bytes` is the
sum of their sizes, what `ls -l` shows. They differ for sparse and compressed
files, and because space is allocated in whole blocks.

### Every directory, as it is measured

```python
from dirsize import iter_dirs

for folder in iter_dirs("my_project"):
    print(folder.disk_bytes, folder.path)
```

Directories stream children first and the root last, like `du` without `-s`.
Each `DirUsage` carries the totals for its whole subtree and its `depth`.

### The largest files or folders

```python
from dirsize import largest

for item in largest("my_project", 5):
    print(item.disk_bytes, item.path)

for item in largest("my_project", 3, kind="dir", by="apparent"):
    print(item.apparent_bytes, item.path)
```

Only `n` items are kept in memory while the tree is walked.

### Options

```python
from dirsize import scan

scan("my_project", follow_symlinks=True)  # enter symlinked folders and junctions
scan("my_project", one_filesystem=True)  # skip folders on another device, like du -x
scan("my_project", count_links=True)  # count every hard link, like du -l
scan("my_project", include_dirs=True)  # add the blocks folders take, like du
scan("my_project", on_error="raise")  # stop at the first unreadable path
```

`iter_dirs` takes the same options; `largest` takes all but `include_dirs`.
`on_error` may also be a callable that receives each `OSError` as it happens.

### The simple calls

```python
from dirsize import dir_size, file_count

print(dir_size("my_project"))  # apparent bytes, hard links once
print(file_count("my_project"))  # one per name, links included
```

These two raise on the first unreadable path unless `on_error="ignore"` or a
callable is given, and they skip link loops silently.

## Command line

```
dirsize [-s] [-A] [-h] [-x] [-L] [-l] [--top N] [--json] [PATH ...]
```

Without options it prints the disk usage in bytes of every directory, children
first, like `du`. `-s` prints one total per path, `-A` uses apparent sizes, `-h`
prints sizes such as `1.5K` or `20M` (rounded up, as `du -h` does), `--top N`
lists the N largest files, and `--json` prints one document with the totals and
errors of each path; these three are exclusive. Like `du`, a hard link or a
folder shared by several paths counts only under the first. Errors go to
standard error and the exit status is 1. The same tool runs as
`python -m dirsize`.

## What is counted

- **Hard links.** A file with several names counts once, in the folder where it
  is met first, unless `count_links=True`. Every name still counts as a file.
- **Links.** A symlink below the root, or a Windows junction or other reparse
  point that names another path, counts as a link entry of its own size and is
  not entered. With `follow_symlinks=True` its target is measured instead. The
  root path is always resolved.
- **Cycles.** A folder is entered at most once per device and file id. Like
  `du -L`, a followed link back to a parent is simply not entered again; a
  physical loop (a bind mount or a hard-linked folder) is reported as `cycle`.
  When following links, a dangling one is a `missing` error, as in `du -L`.
- **Disk usage.** On Linux and macOS it is `st_blocks * 512`. On Windows it is
  the allocation NTFS reports for the file (`AllocationSize`), which already
  accounts for compression, sparse ranges and tiny files kept inside the file
  table; links and folders take 0 there.
- **Apparent size.** Only regular files and symlinks have one, as in GNU du;
  folders, devices and pipes add 0.
- **Errors.** Each one becomes a `ScanError` with the path, a kind
  (`permission`, `missing`, `cycle`, `other`) and the system message.

With `include_dirs=True` the totals match GNU `du -sb` (apparent) and
`du -sB1` (disk) on Linux; the test suite checks this against GNU du on
generated trees.

## Why

The standard library has no single call for the size of a directory tree. The
common recipe, summing `os.path.getsize` over `os.walk`, double counts hard
links, ignores what sparse and compressed files really take, walks into
junctions on Windows and can loop forever on a link cycle. `dirsize` is the
`du` primitive as typed functions: one `os.scandir` walk, `(st_dev, st_ino)`
for hard links and cycles, and every error kept next to the result. No
dependencies, `mypy --strict` clean.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
