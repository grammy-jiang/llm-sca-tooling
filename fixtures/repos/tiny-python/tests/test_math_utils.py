"""Tests for tiny.math_utils."""

import pytest
from tiny.math_utils import add, divide


def test_add_positive() -> None:
    assert add(2, 3) == 5


def test_add_negative() -> None:
    assert add(-1, 1) == 0


def test_divide_normal() -> None:
    assert divide(10, 2) == 5.0


def test_divide_by_zero_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
