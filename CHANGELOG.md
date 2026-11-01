# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-01

First stable release and the first one published to PyPI. The public API is the twelve
names of 0.2.0, now promised to stay compatible for the whole 1.x series: `scan`,
`iter_dirs`, `largest`, `dir_size`, `file_count`, `Usage`, `DirUsage`, `FileUsage`,
`ScanError`, `ErrorKind`, `Measure` and `OnError`, with the `dirsize` command and
`python -m dirsize`. The counting rules, errors, command line and JSON document are
described in GUIDE.md.

### Added

- `Usage.size(by)` and `FileUsage.size(by)`, as `DirUsage` already had.
- `largest` is typed per `kind`: `list[FileUsage]` for files, `list[DirUsage]` for
  directories.
- Every public name and method has a docstring with an example that runs as a test,
  and a GUIDE with the exact counting rules, platform details, errors and command line.
- Results pickle under their public names (`dirsize.Usage`).
- The package exports only its documented public names.

### Changed

- Arguments are checked at the call, before anything is read: a path that is not a
  `str` or `os.PathLike[str]` (bytes included) raises `TypeError`, a path with a NUL
  character `ValueError`; `largest` raises `TypeError` for an `n` that is not an `int`
  (a `bool` included). Error messages quote at most 40 characters of a bad value.
- `DirUsage.size` raises `ValueError` for an unknown `by` instead of returning the
  apparent size.
- `Usage.ok` is false when the path itself was not measured.
- An unreadable subdirectory yields its own `DirUsage` with one error and its own
  blocks (with `include_dirs`), and counts in its parent's `dirs`, as `du` lists it.
- A symlink loop that Windows refuses to resolve is a `cycle` error, as ELOOP is on
  POSIX.
- `iter_dirs` returns a generator; closing it closes every open directory listing.
- The command line prints each error as it happens, and `--top` shares hard links and
  folders across its paths as the other modes do.

### Fixed

- `-h` rounded some sizes above 2**53 bytes down, because it used floating point; it
  now follows `du -h` in exact integers (`1152921504606846977` bytes print as `1.1E`),
  and sizes from 1024 EiB up use `Z`, `Y`, `R` and `Q` as `du` does.
- The command line no longer fails with a traceback when its output pipe closes
  (`dirsize | head`): it stops quietly with status 1. It prints file names the output
  cannot encode as raw bytes on POSIX, as `du` does, or with backslash escapes, instead
  of failing.
- Usage error messages are cut at 300 characters.

## [0.2.0]

### Added

- `scan` returns a typed `Usage`: disk and apparent bytes, files, directories,
  links and every error met, as `ScanError` values.
- Disk usage: `st_blocks` on POSIX, the NTFS allocation size on Windows
  (compression, sparse files and tiny files included).
- `iter_dirs` streams per-directory totals, children before parents.
- `largest` returns the biggest files or directories with bounded memory.
- Options `one_filesystem`, `count_links` and `include_dirs`, matching
  `du -x`, `du -l` and the way `du` counts directories.
- The `dirsize` command and `python -m dirsize`, with `-s`, `-A`, `-h`, `-x`,
  `-L`, `-l`, `--top` and `--json`.

### Fixed

- Windows junctions and other reparse points naming another path are no longer
  entered unless `follow_symlinks=True`. A junction pointing at a parent used to
  recurse until the path grew too long.
- A physical directory loop is reported as a `cycle` error by `scan`; a
  followed link back to a parent is skipped silently, as `du -L` does.

### Changed

- `dir_size` and `file_count` on a file path now measure that file instead of
  raising `NotADirectoryError`.
- With `follow_symlinks=True`, a file reached through two links counts once.
- A symlink below the root counts with its own size (`lstat`), as `du` does.

## [0.1.0]

- First release.
- `dir_size`: total size in bytes of a directory tree, with hardlink dedupe.
- `file_count`: number of files in a directory tree.
- `follow_symlinks` option with loop detection, and `on_error` raise, ignore or callback.
