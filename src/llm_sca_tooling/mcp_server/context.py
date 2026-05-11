"""Server context and lifecycle-owned state."""

from __future__ import annotations

from typing import Any

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
        sampling_client: Any | None = None,
    ) -> None:
        self.workspace = workspace
        self.config = config
        self.capabilities = capabilities
        self.authorization_context_hash = authorization_context_hash
        self.sampling_client: Any | None = sampling_client

    def with_sampling_client(self, client: Any | None) -> McpRequestContext:
        """Return a shallow copy of this context with a per-request sampling client."""
        return McpRequestContext(
            self.workspace,
            self.config,
            self.capabilities,
            authorization_context_hash=self.authorization_context_hash,
            sampling_client=client,
        )
