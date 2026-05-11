"""Tests for the core module."""

from pkg.core import Greeter, compute


def test_compute_add() -> None:
    assert compute(2, 3) == 5


def test_greeter_greet() -> None:
    g = Greeter("alice")
    assert g.greet() == "Hello, Alice!"


class TestCompute:
    def test_zero(self) -> None:
        assert compute(0, 0) == 0
