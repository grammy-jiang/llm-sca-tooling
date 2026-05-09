"""Fixture API layer."""

from __future__ import annotations

from multi.models import Item
from multi.processor import title


def describe(name: str, count: int) -> str:
    item = Item(name=name, count=count)
    return f"{title(item)}:{item.count}"
