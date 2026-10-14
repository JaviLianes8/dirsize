from __future__ import annotations

import pytest

from dirsize._cli import human


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0"),
        (1023, "1023"),
        (1024, "1.0K"),
        (1025, "1.1K"),
        (10 * 1024 - 1, "10K"),
        (10 * 1024, "10K"),
        (1024 * 1024 - 1, "1.0M"),
        (1536 * 1024, "1.5M"),
    ],
)
def test_human_format(size: int, text: str) -> None:
    assert human(size) == text


def test_human_caps_at_the_largest_unit() -> None:
    assert human(1 << 70).endswith("E")
