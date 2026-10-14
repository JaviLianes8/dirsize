# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
