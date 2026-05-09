"""LSP capability models."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class LspClientCapabilities(StrictBaseModel):
    text_document: JsonObject = Field(default_factory=lambda: {"documentSymbol": {}, "definition": {}, "references": {}, "diagnostic": {}})
    workspace: JsonObject = Field(default_factory=lambda: {"symbol": {}})

    def as_lsp(self) -> JsonObject:
        return {"textDocument": self.text_document, "workspace": self.workspace}


class LspServerCapabilities(StrictBaseModel):
    server_id: str
    capabilities: JsonObject = Field(default_factory=dict)
