from __future__ import annotations

from multi.api import describe


def test_describe() -> None:
    assert describe("widget", 2) == "Widget:2"
