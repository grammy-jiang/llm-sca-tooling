"""Configuration for the code-intelligence MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["McpServerConfig"]


class McpServerConfig(BaseModel):
    """Runtime configuration for the local MCP server."""

    model_config = ConfigDict(extra="forbid")

    workspace_path: Path = Path()
    server_name: str = "code-intelligence"
    server_version: str = "0.1.0"
    transport: Literal["stdio", "http"] = "stdio"
    single_user: bool = True
    enable_tasks: bool = True
    enable_task_list: bool = False
    enable_task_cancel: bool = True
    task_ttl_seconds_default: int = Field(default=3600, ge=1)
    task_ttl_seconds_max: int = Field(default=86_400, ge=1)
    task_poll_interval_seconds: int = Field(default=1, ge=1)
    resource_subscription_enabled: bool = True
    sampling_enabled: bool = True
    max_resource_bytes: int = Field(default=1_000_000, ge=1)
    max_graph_slice_nodes: int = Field(default=500, ge=1)
    max_graph_slice_edges: int = Field(default=1_000, ge=1)
    redaction_policy: Literal["redacted", "allow_absolute_paths"] = "redacted"
    telemetry_enabled: bool = True
    in_memory_workspace: bool = False

    @property
    def task_listing_allowed(self) -> bool:
        """Return whether broad task listing is allowed by local policy."""
        return self.single_user and self.enable_task_list
