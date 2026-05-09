"""LSP error types."""


class LspError(Exception):
    """Base LSP client error."""


class LspTimeout(LspError):
    """Raised when an LSP request times out."""


class LspCrash(LspError):
    """Raised when the LSP process exits unexpectedly."""
