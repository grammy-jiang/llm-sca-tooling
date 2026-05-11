"""Core module with simple functions and a class."""

from pkg.helpers import format_name


class Greeter:
    """A simple greeter class."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return f"Hello, {format_name(self.name)}!"


def compute(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y
