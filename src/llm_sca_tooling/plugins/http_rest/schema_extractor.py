"""Schema hint extraction for HTTP routes."""

from __future__ import annotations


def schema_hint_from_parameters(parameters: list[str]) -> dict | None:
    if not parameters:
        return None
    return {"type": "object", "properties": {name: {"type": "string"} for name in parameters}}
