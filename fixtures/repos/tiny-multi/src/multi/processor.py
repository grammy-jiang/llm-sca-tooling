"""Fixture processor with a latent static type issue."""

from __future__ import annotations

from multi.models import Item


def title(item: Item) -> str:
    return item.name.title()


def count_label(item: Item) -> str:
    return item.count
