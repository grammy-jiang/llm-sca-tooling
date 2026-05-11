"""Simple math utilities.

Contains an intentional divide-by-zero bug in ``divide`` for fault-localisation
test fixtures (Phase 9+).
"""


def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


def divide(a: int, b: int) -> float:
    """Return a / b.

    Bug: does not guard against b == 0. Raises ZeroDivisionError when b is 0.
    This is intentional for fault-localisation testing.
    """
    return a / b
