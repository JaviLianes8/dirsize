# dirsize 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to dirsize. Nothing has been published to
PyPI under this name (https://pypi.org/pypi/dirsize/json answered 404 on 2026-10-23), so
1.0.0 is the first upload and there is no installed release to upgrade from. The changes
are listed against 0.2.0, the last version on `main` (29d1a96).

Progress:
- [x] Branch `release/1.0.0` created from `main` (29d1a96, 0.2.0)
- [x] Baseline gates on 0.2.0
- [ ] API review and 1.0.0 changes (item 1)
- [ ] Errors, typing, docstrings and doctests (items 2 to 5)
- [ ] Ground truth: GNU du run in this session, NTFS layout from fsutil, fetched sources (item 7)
- [ ] Contract, fuzz and author mutation round (items 6, 9, 18)
- [ ] Docs: README, GUIDE, CHANGELOG (items 11, 12)
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
