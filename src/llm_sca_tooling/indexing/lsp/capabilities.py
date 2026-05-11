"""Minimal LSP capability declarations."""

from __future__ import annotations

from typing import Any

__all__ = ["client_capabilities"]


def client_capabilities() -> dict[str, Any]:
    return {
        "textDocument": {
            "documentSymbol": {"dynamicRegistration": False},
            "definition": {"dynamicRegistration": False},
            "references": {"dynamicRegistration": False},
            "diagnostic": {"dynamicRegistration": False},
        },
        "workspace": {"symbol": {"dynamicRegistration": False}},
    }
