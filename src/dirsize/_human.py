"""Sizes printed the way ``du -h`` prints them, with exact integer arithmetic."""

from __future__ import annotations

# The unit letters of gnulib's human.c, the code behind du -h: 1024**1 up to 1024**10.
_LETTERS = "KMGTPEZYRQ"
_BASE = 1024


def human(size: int) -> str:
    """Format ``size`` bytes like ``du -h`` in the C locale.

    Binary units (``K`` is 1024), rounded up, one decimal below 10. This follows
    gnulib's ``human_readable`` with ceiling rounding step by step, in exact
    integers, so it agrees with GNU du for every size.

    >>> human(1023), human(1024), human(1025), human(10239), human(1048575)
    ('1023', '1.0K', '1.1K', '10K', '1.0M')
    """
    amount, tenths, rounding, exponent, point = size, 0, 0, 0, ""
    if amount >= _BASE:
        while True:
            # rounding: 0 exact, 1 below a half tenth, 2 exactly half, 3 above it
            r10 = (amount % _BASE) * 10 + tenths
            r2 = (r10 % _BASE) * 2 + (rounding >> 1)
            amount //= _BASE
            tenths = r10 // _BASE
            above = 2 + int(r2 + rounding > _BASE)
            rounding = int(r2 + rounding != 0) if r2 < _BASE else above
            exponent += 1
            if amount < _BASE or exponent == len(_LETTERS):
                break
        if amount < 10:
            if rounding > 0:
                tenths, rounding = tenths + 1, 0
                if tenths == 10:
                    amount, tenths = amount + 1, 0
            if amount < 10:
                point, tenths = f".{tenths}", 0
    if tenths + rounding > 0:
        amount += 1
        if amount == _BASE and exponent < len(_LETTERS):
            amount, exponent, point = 1, exponent + 1, ".0"
    return f"{amount}{point}{_LETTERS[exponent - 1] if exponent else ''}"
