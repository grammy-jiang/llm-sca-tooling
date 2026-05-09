from __future__ import annotations

from tiny.math_utils import add, divide


def test_add() -> None:
    assert add(2, 3) == 5


def test_divide_non_zero() -> None:
    assert divide(6, 3) == 2
