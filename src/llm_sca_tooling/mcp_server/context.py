"""Server context and lifecycle-owned state."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.capabilities import ServerCapabilities
from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.storage import WorkspaceStore


class McpRequestContext:
    def __init__(
        self,
        workspace: WorkspaceStore,
        config: McpServerConfig,
        capabilities: ServerCapabilities,
        *,
        authorization_context_hash: str | None = None,
    ) -> None:
        self.workspace = workspace
        self.config = config
        self.capabilities = capabilities
        self.authorization_context_hash = authorization_context_hash
