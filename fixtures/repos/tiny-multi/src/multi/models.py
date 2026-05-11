"""Simple dataclass models."""

from dataclasses import dataclass


@dataclass
class Item:
    item_id: str
    value: int
