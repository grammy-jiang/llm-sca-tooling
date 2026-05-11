"""Shared JSON-RPC/LSP client primitives."""

from llm_sca_tooling.indexing.lsp.client import LspClient
from llm_sca_tooling.indexing.lsp.errors import LspError, LspTimeout

__all__ = ["LspClient", "LspError", "LspTimeout"]
