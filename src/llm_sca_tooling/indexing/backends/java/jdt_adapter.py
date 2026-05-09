"""Minimal Java parser adapter."""

from __future__ import annotations

import re


def extract_java_symbols(text: str) -> list[tuple[str, str]]:
    symbols = []
    for match in re.finditer(r"\bclass\s+([A-Za-z_]\w*)", text):
        symbols.append(("class", match.group(1)))
    for match in re.finditer(
        r"\b(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_]\w*\s+([A-Za-z_]\w*)\s*\(",
        text,
    ):
        symbols.append(("method", match.group(1)))
    return symbols
