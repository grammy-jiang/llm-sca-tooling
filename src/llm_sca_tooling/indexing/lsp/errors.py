"""LSP error types."""


class LspError(Exception):
    """Base LSP client error."""


class LspTimeout(LspError):  # noqa: N818
    """Raised when an LSP request times out."""


class LspCrash(LspError):  # noqa: N818
    """Raised when the LSP process exits unexpectedly."""
