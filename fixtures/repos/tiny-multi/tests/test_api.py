"""Tests for the multi fixture API."""

from multi.api import scale_item


def test_scale_item_basic() -> None:
    assert scale_item("x", 5, 3) == 15


def test_scale_item_zero() -> None:
    assert scale_item("y", 0, 100) == 0
