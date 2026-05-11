"""Item processor.

Contains an intentional latent type error: ``process`` multiplies ``item.value``
(int) by a string multiplier — type-correct at runtime when multiplier is int,
but the annotation ``str`` is wrong. This is intentional for SARIF / type-checking
test fixtures (Phase 6+).
"""

from multi.models import Item


def process(item: Item, multiplier: str) -> int:  # bug: multiplier should be int
    """Process an item by scaling its value.

    Bug: ``multiplier`` is annotated as ``str`` but used as ``int``.
    mypy and similar tools will flag this as a type error.
    """
    return item.value * multiplier  # type: ignore[return-value,operator]
