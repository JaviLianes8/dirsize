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
- [ ] Author mutation round (item 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and every Python (items 8, 10, 13, 14)
- [ ] Gates (item 15)
- [ ] PR and trace guard CLEAN
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)

## Baseline on 0.2.0 (before any change)

On this PC (CPython 3.13.2, Windows 11), at 29d1a96: `ruff format --check .`,
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
