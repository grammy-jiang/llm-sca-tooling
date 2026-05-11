"""LSP client errors."""

from __future__ import annotations

__all__ = ["LspError", "LspTimeout"]


class LspError(Exception):
    """Base LSP client failure."""


class LspTimeoutError(LspError):
    """Raised when an LSP request exceeds its timeout."""


LspTimeout = LspTimeoutError
