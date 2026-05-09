"""Shared JSON-RPC/LSP support."""

from llm_sca_tooling.indexing.lsp.client import LspClient
from llm_sca_tooling.indexing.lsp.errors import LspCrash, LspError, LspTimeout

__all__ = ["LspClient", "LspCrash", "LspError", "LspTimeout"]
