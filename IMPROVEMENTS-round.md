# dirsize improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Typed results and errors (`Usage`, `DirUsage`, `FileUsage`, `ScanError`)
- [x] Walker: junctions and other name-surrogate reparse points not followed, cycles, one filesystem
- [x] Disk usage: `st_blocks` on POSIX, compressed and sparse aware allocation on Windows
- [x] Streaming per-directory totals, top-N largest files and directories
- [x] CLI (`dirsize PATH...`, `python -m dirsize`) with JSON output
- [x] Docs: README, CHANGELOG, docstrings, runnable README examples
- [x] Contracts, GNU du oracle (WSL), installed wheel e2e, mutation run
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [x] Independent review findings fixed
- [x] Pull request opened (#2), guard clean

Every item is additive. `dir_size`, `file_count` and `OnError` keep their names,
signatures and return values on ordinary trees.

## Starting point

`0.1.0` walks with `os.scandir`, sums `st_size` of every non-directory entry,
dedupes hard links by `(st_dev, st_ino)` and detects loops only when following
symlinks. Gaps found while reading `_core.py`:

- On Windows a directory junction is not a symlink to `DirEntry.is_symlink`, and
  `is_dir(follow_symlinks=False)` is true for it, so junctions are always walked.
  A junction pointing at an ancestor recurses until the path is too long, and a
  junction to another folder counts that folder twice.
- Only the apparent size exists. A sparse or NTFS compressed file reports its full
  logical length, so the total can be far above the space actually used.
- No way to see which directories or files are large, no streaming, no partial
  result next to the errors: `on_error="ignore"` drops them silently.
- No command line entry point.

## Sources (fetched 2026-10-14)

- GNU coreutils manual source, `du invocation` node:
  https://raw.githubusercontent.com/coreutils/coreutils/master/doc/coreutils.texi
  (sha256 `c6cfceb6...`). Default is file system usage, `--apparent-size` gives
  `st_size`; when several hard links point to one file only one is counted, and
  argument order decides which; `-l` counts every link; `-x` skips directories on
  other file systems than the argument; `-L` dereferences every symlink, `-D` only
  command line ones; a sparse file has a large apparent size but uses little space.
- du(1) man page: https://man7.org/linux/man-pages/man1/du.1.html (same options).
- Python `os` docs: https://docs.python.org/3/library/os.html (`st_blocks` counts
  512-byte blocks and can be below `st_size / 512` for files with holes;
  `st_reparse_tag` is set when the reparse point attribute is present;
  `DirEntry.is_junction` from 3.12).
- `GetCompressedFileSizeW`: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getcompressedfilesizew
  (returns the compressed or sparse allocated size; for other files the plain
  size; follows a symbolic link to its target).
- `FILE_STANDARD_INFO`: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info
  (`AllocationSize` is the space allocated for the file).
- GNU du source: https://raw.githubusercontent.com/coreutils/coreutils/master/src/du.c
  (apparent size only for types with a usable `st_size`; every file is hashed
  for hard-link dedupe when dereferencing all links).
- Reparse point tags: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-tags
  (`IsReparseTagNameSurrogate`: the bit that marks a tag as naming another entity,
  set for symlinks and mount points; cloud and dedup tags do not set it).

GNU du runs only as a test oracle. In this WSL image `du` is the uutils port, so
the oracle uses `du` only when it says it is GNU, and `gnudu` otherwise.

## Ranked improvements

1. **Links are not followed by default, junctions included.** Symlinks and any
   reparse point whose tag is a name surrogate (junctions, mount points, symlinks)
   are counted as the link itself and never entered unless `follow_symlinks=True`.
   This fixes the junction loop and double count.
2. **Cycles always safe.** Every directory is entered at most once per
   `(st_dev, st_ino)`; in a physical walk re-entering an ancestor is reported as
   a `cycle` error, as GNU du warns about a circular directory structure; with
   `-L` du skips such a loop silently, and so does dirsize.
3. **Disk usage next to apparent size.** `Usage.disk_bytes`: `st_blocks * 512` on
   POSIX; on Windows the `AllocationSize` NTFS reports in `FILE_STANDARD_INFO`,
   so compressed and sparse files show what they really take. (The first version
   used `GetCompressedFileSizeW` rounded up to the cluster size; review showed
   it counts a whole cluster for tiny files kept inside the file table.) When
   the platform cannot tell, it falls back to the apparent size.
4. **Typed results with errors kept.** `scan(path) -> Usage` (apparent bytes, disk
   bytes, files, directories, links, errors). Errors become `ScanError(path, kind,
   message)` (`permission`, `missing`, `cycle`, `other`) and the scan goes on;
   `on_error="raise"` stops at the first one.
5. **GNU options.** `one_filesystem` (`-x`), `count_links` (`-l`),
   `follow_symlinks` (`-L`), `include_dirs` to add each directory's own entry
   size as du does, so totals match `du -sb` and `du -sB1`.
6. **Streaming.** `iter_dirs(path)` yields a `DirUsage` per directory in post
   order (children before parents, like `du` without `-s`), with constant memory
   besides the walk stack and the hard-link set.
7. **Top-N.** `largest(path, n, by="disk"|"apparent", kind="file"|"dir")` keeps a
   bounded heap while streaming.
8. **CLI.** `dirsize PATH...` prints `du`-style lines, `-s`, `-A/--apparent-size`,
   `-x`, `-L`, `-l`, `-H` human sizes, `--top N`, `--json`; exit 1 when any error
   was reported, like du.
9. **Docs.** Docstrings, README covering semantics per platform, README examples
   executed by the test suite, CHANGELOG `0.2.0`.
10. **Proof.** Contract test of the public surface, behaviour tests on built trees
    (hard links, symlinks, junctions, compressed and sparse files, permission
    errors, cycles), a GNU du oracle on random trees in WSL, an installed wheel e2e
    driving the CLI, and a mutation run over the walker and size code.

## Results

- GNU du 9.7 (`gnudu` in WSL Ubuntu) agrees with `scan` and `iter_dirs` on 12
  seeded random trees with hard links, symlinks to files and folders and sparse
  files: `-sb`, `-sB1`, `-b`, `-B1` per directory, `-l` and `-L`. Matching it
  showed that du gives folders, devices and pipes no apparent size, and that
  with `-L` every file is deduplicated by device and inode, not only files
  with several hard links. Both rules are now implemented.
- Mutation run (43 hand-written mutants over the walker, platform, types, API
  and CLI, no bytecode, caches purged, 180 s per mutant, baseline green before
  and after): 40 killed on Windows. The two `include_dirs` mutants survive only
  where folders take no blocks (NTFS here, tmpfs); they are killed on ext4 in
  WSL. The last one, skipping non-regular files before asking Windows for the
  compressed size, is equivalent: Windows reports 0 for a folder anyway.
- The installed wheel test builds, installs into a fresh venv and drives the
  `dirsize` command and the API (`DIRSIZE_E2E=1`).

## Independent review

Twelve findings, fixed with regression tests unless noted:

- With `-L`, a link back to a parent is skipped silently, as du does; only a
  physical loop is a `cycle` error.
- The claim that `du -L` counts a dangling link silently did not hold: GNU du
  9.7 prints "cannot access" and exits 1. The oracle now builds dangling links
  and loops, and checks error counts as well as sizes.
- The CLI shares one set of seen files and folders across its paths, so a hard
  link or folder counts once and a repeated path prints once, like du. An
  oracle test compares the CLI output with du byte for byte.
- Windows disk usage is now the NTFS `AllocationSize`: tiny files kept in the
  file table no longer count a whole cluster, and the cluster cache is gone.
- `largest` takes `count_links`, and the CLI passes `-l` to `--top`.
- `-s`, `--top` and `--json` are exclusive. `-x`, `-L` and `-l` each have a
  test of their effect. `-h` prints bytes without a unit, like du.
- An unreadable root still yields its own line with the error counted.
- The README, the docstrings and the CHANGELOG were corrected: options of
  `largest`, memory use of `iter_dirs`, no speed claim, and the behaviour
  changes of `dir_size` and `file_count`.

## Out of scope

Parallel walking, ignore patterns, caching between runs, and per-user quotas.
Alternate data streams on NTFS are not added to the apparent size.
