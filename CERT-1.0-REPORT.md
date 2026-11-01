# dirsize 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to dirsize. Nothing has been published to
PyPI under this name (https://pypi.org/pypi/dirsize/json answered 404 on 2026-11-01), so
1.0.0 is the first upload and there is no installed release to upgrade from. The changes
are listed against 0.2.0, the last version on `main` (29d1a96).

Progress:
- [x] Branch `release/1.0.0` created from `main` (29d1a96, 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Ground truth: GNU du and numfmt run locally, fetched sources (item 7)
- [x] Contract and seeded tree properties (items 6, 9)
- [x] Author mutation round (item 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and every Python (items 8, 10, 13, 14)
- [x] Gates (item 15)
- [x] PR #3 open and trace guard CLEAN
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)

## Baseline on 0.2.0 (before any change)

The earlier run recorded CPython 3.13.2 on Windows at 29d1a96: `ruff format --check .`,
`ruff check .` and `mypy --strict src tests` exit 0; `pytest` passed with 67 skips (60 GNU du
oracle tests, which need a POSIX system with GNU coreutils; 5 permission tests, because this
account can read a folder it is denied; the installed-wheel test without `DIRSIZE_E2E=1`; the
POSIX sparse file test). No doctests existed.

## Preparation resumed 2026-11-01

Continued the two existing release commits without replacing them. No earlier QA
verdicts were recorded. The added contracts pin the public signatures, result methods,
pickles, frozen values, error families, input validation and public exports. Three
seeded trees (180 entries each) are checked against a flat inventory; 1,000 generated
invalid options have bounded errors, and a 100-level tree works with recursion limited
to 80. Documentation examples run as part of the suite.

## Ground truth

The URLs, revisions, fetch dates, sizes, licences and SHA-256 values are recorded in
`tests/references.json`. `scripts/fetch_references.py DIRECTORY` downloads the text
outside the repository; `DIRSIZE_REFERENCES` enables the hash checks. No downloaded
text is committed or distributed. The sources are the GNU coreutils v9.5 manual,
Microsoft FILE_STANDARD_INFO documentation, and Python 3.14 os documentation.

GNU du 8.32 and numfmt 8.32 from Git for Windows were executed on 2026-11-01.
`tests/test_references.py` compares three seeded trees, both hard-link modes, apparent
and allocated bytes, and a real sparse file against du. It compares 2,007 byte counts
against numfmt ceiling rounding. The cases are generated inputs, not official vectors.
The bounded os.walk experiment confirms that a Windows junction revisits its target.

The MSYS du port differs for tiny NTFS resident files: a one-byte file reports 1,024
bytes there, whereas FILE_STANDARD_INFO reports 8 bytes. The library uses the latter;
this difference is not claimed as oracle agreement. `fsutil file queryextents` on a
5,000-byte ordinary file reports two clusters and both du and dirsize report 8,192
bytes. `fsutil file layout` is unavailable to this account (access denied).

## Contract strength (item 18)

Eighteen deliberate mutations were applied one at a time in a separate copy, with
bytecode disabled, the suite run with `-x`, a 300-second process limit and the normal
300-second per-test limit. Every change was restored immediately afterwards. Seventeen
failed initially. M05 survived because this Windows account cannot create symlinks and
a junction is still a directory in lstat. A synthetic root-symlink metadata contract
was added; M05 then failed. All eighteen are now caught. Real junction tests also run.

| ID | Deliberate bug | Test that failed |
| --- | --- | --- |
| M01 | drop child directory count | `tests/test_docs.py::test_every_doc_example_prints_what_its_comments_say[README-3]` |
| M02 | disable hard-link deduplication | `tests/test_cli.py::test_hard_link_shared_by_two_paths_counts_once` |
| M03 | drop nested errors | `tests/test_errors.py::test_errors_are_counted_on_the_directory_that_holds_them` |
| M04 | drop link count | `tests/test_links.py::test_junction_is_not_entered_by_default` |
| M05 | do not resolve a root symlink | `tests/test_contract_io.py::test_root_symlink_stat_is_resolved_before_selecting_file_or_directory` |
| M06 | double POSIX allocation unit | `tests/test_disk.py::test_posix_disk_bytes_are_512_byte_blocks` |
| M07 | off-by-one Windows allocation | `tests/test_disk.py::test_disk_bytes_follow_ntfs_allocation` |
| M08 | ignore measured status in ok | `tests/test_contract_values.py::test_usage_defaults_and_ok_are_independent` |
| M09 | wrong negative count error type | `tests/test_docs.py::test_every_doc_example_prints_what_its_comments_say[GUIDE-5]` |
| M10 | select smallest instead of largest | `tests/test_cli.py::test_top_lists_the_largest_files` |
| M11 | use decimal size units | `tests/test_docs.py::test_every_docstring_example_passes` |
| M12 | misclassify missing paths | `tests/test_docs.py::test_every_doc_example_prints_what_its_comments_say[GUIDE-5]` |
| M13 | swap apparent and disk results | `tests/test_cli.py::test_default_lists_every_directory_children_first` |
| M14 | wrong child depth | `tests/test_contract_io.py::test_closing_a_partial_walk_releases_all_listings` |
| M15 | accept boolean counts | `tests/test_contract_values.py::test_largest_rejects_non_integer_counts[True]` |
| M16 | forget overlapping ordinary file roots | `tests/test_contract_io.py::test_overlapping_file_and_directory_roots_share_file_identity` |
| M17 | unbounded invalid values | `tests/test_contract_values.py::test_nul_and_bad_error_policy_fail_eagerly[scan]` |
| M18 | repeat file roots | `tests/test_contract_io.py::test_cli_repeated_file_root_is_counted_once[mode0]` |

## Packaging checks

The wheel and source archive were built locally using hatchling 1.33.0. Both pass
`twine check --strict`. The installed-wheel test runs from a temporary consumer folder,
installs into a new venv, invokes both the console script and `python -I -m dirsize`,
and checks the API, `py.typed`, version, directory listing, summary, human formatting,
largest files, JSON and missing-path exit status. No source import is used by the
consumer. There is no published PyPI version to upgrade from (live JSON endpoint 404).

Wheel contents: thirteen Python modules, `py.typed`, metadata, console entry point,
RECORD and MIT LICENSE. Source archive: source, tests, the reference metadata manifest,
README, GUIDE, CHANGELOG, CONTRIBUTING, project settings and maintenance scripts.
Neither archive contains fetched documentation, scratch output, bytecode, caches or
certification reports. Runtime dependencies are empty; development extras are optional.

## Interpreter matrix

Twelve distinct installed interpreter builds were found and exercised locally. Stale
Python-launcher entries pointing to deleted executables were excluded. Identical
copies of the same build were deduplicated. For each build, the suite runs against
the installed wheel with the source directory removed from its import path, in an
isolated venv or a private copy of an embedded runtime. The CLI version runs as a
subprocess from outside the repository. All twelve pass.

| Python | Build | Result |
| --- | --- | --- |
| 3.14.6 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.11.11 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.13.18 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.12.16 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.11.18 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.10.22 | standard | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.13.2 | standard | 166 passed, 74 skipped |
| 3.12.10 | standard | 166 passed, 74 skipped |
| 3.11.9 | standard | 166 passed, 74 skipped |
| 3.10.11 | standard | 166 passed, 74 skipped |
| 3.14.10 | free-threaded | 165 passed, 74 skipped; 11 updated contracts passed |
| 3.14.10 | standard | 165 passed, 74 skipped; 11 updated contracts passed |

The four embedded runtimes initially could not collect the opt-in build test because
`venv` is absent; that import now occurs only inside the test. Their complete suites
then pass. The other eight builds additionally run the final root-symlink contract
and the updated collection checks after their full suites. No supported Python minor
version is unavailable: 3.10, 3.11, 3.12, 3.13 and 3.14 all ran. The matrix skips the
60 POSIX-only GNU tree cases, 12 native symlink cases lacking Windows privileges,
one POSIX sparse-file case, and the separately executed wheel build test.

A strict external consumer of the installed wheel passes `mypy --strict`, including
`largest` return types for both kinds. A separate 1,000/4,000-file run measured scan
at 0.111/0.480 seconds and largest(n=10) at 0.125/0.464 seconds. Those local timings
support linear traversal for these trees; they are not a universal performance bound.

## Preparation scorecard

| Item | Status | Evidence |
| --- | --- | --- |
| 1 | PASS | Twelve public names and defaults pinned; all changes from source 0.2.0 in CHANGELOG |
| 2 | PASS | Exact exports, no accidental public imports, public-only documentation examples |
| 3 | PASS | Public names and methods have executed examples; README and GUIDE examples pass |
| 4 | PASS | Strict source, tests and installed-consumer typing; py.typed in both archives |
| 5 | PASS | Documented TypeError, ValueError and OSError policies; bounded argument and usage errors |
| 6 | PASS | Value, traversal, error, link, CLI, streaming and installed-wheel contracts |
| 7 | PASS | Live GNU programs, fetched specification metadata, NTFS sparse and compressed files |
| 8 | PASS | Fresh wheel venv, API and both CLI entry points; PyPI has no prior release |
| 9 | PASS | Seeded trees, 1,000 invalid inputs, 2,007 formatting oracle cases, deep tree and scaling |
| 10 | PASS | Twelve installed builds, every supported minor version, free-threaded Python included |
| 11 | PASS | Exact certification badge, absolute links, verified alternatives, strict twine check |
| 12 | PASS | CHANGELOG 1.0.0 dated 2026-11-01 |
| 13 | PASS | 1.0.0, Production/Stable, accurate classifiers, MIT, URLs, no runtime dependencies |
| 14 | PASS | Both archive listings inspected and assertions in the wheel test |
| 15 | PASS | Each of the four gates exits 0 independently |
| 16 | PENDING | Independent review is a separate stage |
| 17 | READY | PR #3 open, trace guard CLEAN; merge and publication are separate stages |
| 18 | PASS | All eighteen mutations caught, including the initial survivor after a new contract |
| 19 | PENDING | No independent lens verdicts are recorded yet |

## Final gates

On 2026-11-01, each command exits 0 on its own: `ruff format --check .`,
`ruff check .`, `mypy --strict src` (13 source files), `mypy --strict src tests`
(30 files), and `pytest` (167 passed, 73 skipped). The pytest run enables
`DIRSIZE_E2E=1`, the two GNU executable paths (`DIRSIZE_DU`, `DIRSIZE_NUMFMT`),
and `DIRSIZE_REFERENCES`. Temporary files, builds and pytest basetemp are outside
the repository in a dedicated validation directory. Every test has a 300-second
timeout. The 73 skips are the platform cases listed above; the wheel test runs.

PR: https://github.com/JaviLianes8/dirsize/pull/3, from `release/1.0.0` to `main`.
The preparation stage does not merge or publish. Items 16 and 19 remain pending.
