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
- [x] QA round 1 findings corrected and regression contracts added
- [x] QA round 2 findings corrected and all eleven surviving mutations caught
- [x] QA round 3 recursive exception state fixed and all three surviving mutations caught
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

## QA lenses: round 1 fixes (2026-11-01)

Reviewed base: `9418522ec948ff5940d134be200c579a61637424`, branch `release/1.0.0`.
Fix commit: `ac3c46a3a72abbec2da4e0699d26b6a538f4ba17`
(`fix qa round one contracts and diagnostics`).
All 19 findings are addressed below. Independent lens rechecks remain pending;
this fix round does not replace their verdicts or mark item 19 as passed.

Behavior contracts were added before implementation: the initial focused run
had 23 failures and 9 passes, reproducing every reported behavior bug. After the
fixes, the four new contract modules passed all 47 cases. Existing assertions for
the old unreadable-root flag and CLI diagnostic format were updated accordingly.

| Finding | Change and verification |
| --- | --- |
| A-001, B-01 | Root listing-open failures return `measured=False`, zero totals and the retained permission record in `scan` and CLI JSON; both `include_dirs` modes use controlled nonzero allocation. |
| A-002 | Preserve and document synthetic regular-file `DirUsage` roots in README, GUIDE and API docstrings; pin the path, bytes, counts and depth for both operations. |
| A-003 | Each typing alias now has its own source attribute docstring with a runnable example, extracted and executed by name. GUIDE explicitly records this convention for shared typing objects; CHANGELOG no longer claims per-object runtime docstrings. Alias identity and API remain unchanged. |
| B-02 | CLI `--top 0` consumes the walk, reports missing roots and exits 1; the API's existing zero-count validation-only contract remains unchanged. |
| C-01 | Normalize string subclasses before validation, including values returned by `os.PathLike`; all five calls pass hostile string-hook contracts. |
| C-02 | Validation and CLI usage errors omit supplied values, including unknown options and attached arguments; short sentinel contracts pass. |
| C-03 | Raised filesystem exception text and CLI stderr redact paths and system-supplied text; error families and explicit metadata remain available. Short secret and 10,000-character path contracts pass, including `str`, `repr`, `errno`, filename and Windows error code checks. |
| C-04 | Windows paths above 32,767 UTF-16 code units fail at the public call with documented `ValueError`; both ASCII and supplementary Unicode cases cover all five calls, including eager `iter_dirs` validation. |
| E01 | Hard-link contracts check child and root bytes and file totals in `iter_dirs` with both `count_links` values. |
| E02 | Synthetic nonzero directory allocation pins `include_dirs` for root and child totals on every platform. |
| E03 | Controlled foreign-device metadata pins both `largest` kinds with and without `one_filesystem`. |
| E04 | Pin the complete `OnError` alias and strictly type-check a public callback consumer using all five calls. |
| E05 | Synthetic `winerror=1921` must classify as `cycle`. |
| E06 | Preserve error messages with and without `strerror`, and their explicit paths. |
| E07 | Failed Windows allocation queries fall back to plain size. |
| E08 | Synthetic acquired handles close exactly once after successful, failed and exceptional queries; failed opens do not close an unacquired handle. |
| E09 | An ASCII subprocess stream prints the entire escaped accented filename with exact stdout, empty stderr and exit 0. |
| E10 | Buffered stderr instrumentation proves error visibility before measuring the next root. |

The ten surviving lens-e mutations were reapplied individually in a scratch copy.
Each new discriminator failed by assertion, with exit 1; source was restored after
each run. These are additional contracts, not newly discovered production bugs.

| Lens-e mutation | Detecting test in `tests/test_contract_*.py` |
| --- | --- |
| M05 | `accounting.py::test_iter_dirs_counts_hardlinks_in_child_and_root` |
| M11 | `accounting.py::test_directory_allocation_includes_root_and_child` |
| M14 | `accounting.py::test_largest_honours_foreign_device_boundary` |
| M20 | `accounting.py::test_on_error_alias_and_typed_callback_consumer` |
| M24 | `accounting.py::test_windows_loop_code_is_a_cycle` |
| M25 | `accounting.py::test_bare_error_message_is_preserved` |
| M29, M30 | `native.py::test_allocation_queries_close_each_acquired_handle` |
| M37 | `output.py::test_ascii_stdout_preserves_complete_escaped_filename` |
| M38 | `output.py::test_cli_errors_are_flushed_before_next_root` |

Final gates on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src` and `mypy --strict src tests` each exit 0. The complete
`pytest` run exits 0 with **208 passed, 79 skipped**, with `DIRSIZE_E2E=1` enabling
the wheel build, clean installation and CLI consumer. Skips are 12 symlink privilege
cases, one POSIX sparse-file case, 60 POSIX GNU-du cases and six optional external
reference cases. No new interpreter matrix or independent QA verdict is claimed.
All pytest runs use a 300-second per-test timeout and basetemp below
`C:/lianes8-build/codex-pylib/scratch/dirsize-cert/fix-r1/`; logs and mutation
results are retained there. No device-file fixtures were used.

### Disputed findings

None.

## QA lenses: round 2 fixes (2026-11-02)

Reviewed base: `8c8a1e4b1ca359585fcc3bb4079b3ad6291fc7b0`, branch `release/1.0.0`.
Fix commit: `23e1e786502b8a34f0d0c23f286da9d2d634bc37`
(`fix qa round two exception transport and contracts`).
All 16 findings are addressed below. Independent lens rechecks remain pending;
this fix round does not replace their verdicts or mark item 19 as passed.

The three new contract modules were added before implementation. The first run
against the reviewed base had **54 failures and 51 passes**, reproducing missing
exception arguments, failed pickle/process-pool transport and malformed PathLike
diagnostic disclosure. All **105 cases pass** after the fixes. The public API
names, signatures and defaults are unchanged. GUIDE and CHANGELOG describe the
updated exception transport and path-conversion diagnostic behavior.

| Finding | Change and verification |
| --- | --- |
| A-004, B-03, C-06 | A module-level pickle reconstruction function restores the original exception family, args, native metadata, attached attributes and redacted str/repr. Six error cases round-trip with protocols 0 through 5, including repeated serialization. A real missing-file control and a spawned process pool preserve FileNotFoundError. Family names are transported explicitly so old protocols cannot remap them to OSError. |
| C-05 | Restore args explicitly instead of relying on the no-op OSError initializer; six synthetic error cases and a native missing-file comparison retain their original arguments. |
| C-07 | Normalize TypeError from path conversion to a fixed diagnostic and suppress its original context. All five public calls reject malformed return values without exposing caller-controlled type names in formatted tracebacks. |
| E11 | CLI --top 0 consumes a real file entry followed by a synthetic listing error, closes the listing, prints no rows, reports the error and exits 1. |
| E12 | NUL and overlong CLI paths fail with bounded private usage diagnostics and exit 2 in all four output modes. |
| E13 | Pin 32766, 32767 and 32768 UTF-16 units with ASCII and supplementary characters; equality is admitted without consuming iter_dirs. |
| E14 | Both high and low unpaired surrogates pass eager validation and reach the normal filesystem error callback. |
| E15 | Bytes, None and hostile repr objects fail path validation with bounded diagnostics that omit supplied values. |
| E16 | Invalid string and hostile repr counts fail with bounded private diagnostics. |
| E17 | Raised error str and repr retain the exact category and redaction notice for all six synthetic cases. |
| E18 | Complete formatted tracebacks omit the original sensitive filesystem exception context. |
| E19 | Two-path exceptions retain both filename and filename2, including after serialization. |
| E20 | Raised errors retain strerror independently of their redacted display. |
| E21 | Attached detail metadata survives raising and serialization. |

The eleven surviving lens-e mutations were reapplied individually in a scratch
copy. Every mutation produced an assertion failure and exit 1; clean baselines
before and after restoration passed all 105 cases. N20 and N26 were adapted to
the new reconstruction helper while retaining the reported semantic changes.
These findings required regression contracts, with no production behavior change.

| Finding / mutation | Detecting test in tests/test_contract_*.py |
| --- | --- |
| E11 / N06 | `cli_traversal.py::test_cli_top_zero_reports_error_after_first_file` |
| E12 / N07 | `cli_traversal.py::test_cli_invalid_paths_have_bounded_usage_errors` |
| E13 / N13 | `input_privacy.py::test_windows_utf16_boundary_is_inclusive` |
| E14 / N14 | `input_privacy.py::test_windows_surrogate_path_reaches_error_policy` |
| E15 / N15 | `input_privacy.py::test_malformed_pathlike_diagnostics_are_private` |
| E16 / N16 | `input_privacy.py::test_invalid_counts_have_bounded_private_diagnostics` |
| E17 / N20 | `exception_transport.py::test_raised_error_display_and_traceback_are_redacted` |
| E18 / N21 | `exception_transport.py::test_raised_error_display_and_traceback_are_redacted` |
| E19 / N22 | `exception_transport.py::test_raised_errors_keep_explicit_metadata[filename2]` |
| E20 / N23 | `exception_transport.py::test_raised_errors_keep_explicit_metadata[strerror]` |
| E21 / N26 | `exception_transport.py::test_raised_errors_keep_explicit_metadata[detail]` |

Gates on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src` and `mypy --strict src tests` each exit 0. The complete pytest
run exits 0 with **313 passed, 79 skipped**, including the installed-wheel build,
clean installation and CLI consumer enabled by `DIRSIZE_E2E=1`. Skips are the same
12 symlink privilege cases, one POSIX sparse-file case, 60 POSIX GNU-du cases and
six optional external reference cases as round 1. No new interpreter matrix or
independent QA verdict is claimed.

All pytest runs use a 300-second per-test timeout and a basetemp below
`C:/lianes8-build/codex-pylib/scratch/dirsize-cert/fix-r2-20261102/`.
The failing baseline log, mutation runner, exact edits, detecting test names and
per-mutation logs are retained there. No device-file fixtures were used.

### Disputed findings

None.

## QA lenses: round 3 fixes (2026-11-02)

Reviewed base: `37363d593a2b3bed04031197ed997882a121c469`, branch `release/1.0.0`.
Fix commit: `487bbbbf098c6283d8f9204259de40106fd25032`
(`fix qa round three exception state and contracts`).
All six findings are addressed. Independent lens rechecks remain pending; this
round does not replace their verdicts or mark item 19 as passed.

The new contracts ran before the implementation change: **30 failed, 67 passed**.
The failures reproduce recursive attribute loss for all five public path-taking
calls under pickle protocols 0 through 5, with native FileNotFoundError controls.
After the fix, the focused exception-state, transport and input-privacy contracts
pass all **153 cases**. Public names, signatures and defaults are unchanged.

| Finding | Change and verification |
| --- | --- |
| A-005, B-04, C-08 | Move attached attributes into the reduction tuple's deferred state, applied after exception memoization. Native controls and real missing-path exceptions retain direct and dictionary back-references, an unrelated tag, args, filename, errno and redacted diagnostics. The reconstruction function retains its existing arguments for earlier serialized errors. CHANGELOG records the behavior fix. |
| E22 | Across all five calls, RuntimeError, ValueError and OSError raised by a PathLike hook propagate as the identical exception object. This closes a contract gap without changing production path conversion. |
| E23 | An importable module-level custom OSError family survives protocols 0 through 5, preserving metadata, attached values and safe diagnostics. A native pickle control verifies the fixture is serializable. |
| E24 | A nested custom OSError family with the same short name as a different module-level class retains its actual family through protocols 0 through 5. Native controls and metadata assertions distinguish the qualified name from the short name. |

The three surviving mutations were reapplied individually in an isolated scratch
copy. Each fails with exit 1; original source bytes are restored after each run.
E22, E23 and E24 were missing contracts, not failures in the unmodified code.

| Finding / mutation | Detecting contract | Result |
| --- | --- | --- |
| E22 / S02 | `test_non_typeerror_pathlike_failure_propagates_unchanged` | 15 failures |
| E23 / S16 | `test_pickle_preserves_importable_exception_family` | 12 failures |
| E24 / S17 | `test_pickle_preserves_importable_exception_family` | 6 nested-family failures; 6 module-level cases pass |

Gates on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src` and `mypy --strict src tests` each exit 0. The complete pytest
run exits 0 with **370 passed, 79 skipped**, including the installed-wheel build,
clean installation and CLI consumer enabled by `DIRSIZE_E2E=1`. The skips cover
12 symlink privilege cases, one POSIX sparse-file case, 60 POSIX GNU-du cases and
six optional external reference cases. No new interpreter matrix or independent
QA verdict is claimed.

All pytest runs use a 300-second per-test timeout and dedicated basetemp paths
below `C:/lianes8-build/codex-pylib/scratch/dirsize-cert/fix-r3-20261102/`.
The failing baseline, mutation script, exact edits and per-mutation logs are
retained there. No device-file fixtures were used.

### Disputed findings

None.
