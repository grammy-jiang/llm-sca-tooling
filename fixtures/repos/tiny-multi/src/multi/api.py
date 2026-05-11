"""Public API for the multi fixture package."""

from multi.models import Item
from multi.processor import process


def scale_item(item_id: str, value: int, factor: int) -> int:
    """Create an Item and scale its value by factor."""
    item = Item(item_id=item_id, value=value)
    return process(item, factor)  # type: ignore[arg-type]
