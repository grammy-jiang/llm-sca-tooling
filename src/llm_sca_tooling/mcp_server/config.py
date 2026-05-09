"""MCP server configuration."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import RedactionStatus


class McpServerConfig(StrictBaseModel):
    workspace_path: Path = Path(".llm-sca")
    schema_dir: Path = Path("schemas")
    server_name: str = "code-intelligence"
    server_version: str = "0.1.0"
    transport: str = "stdio-jsonl"
    single_user: bool = True
    enable_tasks: bool = True
    enable_task_list: bool = False
    enable_task_cancel: bool = True
    task_ttl_seconds_default: int = 3600
    task_ttl_seconds_max: int = 24 * 3600
    task_poll_interval_seconds: int = 1
    resource_subscription_enabled: bool = True
    sampling_enabled: bool = True
    max_resource_bytes: int = 1_000_000
    max_graph_slice_nodes: int = 2_000
    max_graph_slice_edges: int = 4_000
    redaction_policy: RedactionStatus = RedactionStatus.REDACTED
    telemetry_enabled: bool = True

    model_config = StrictBaseModel.model_config | {"arbitrary_types_allowed": True}

    @classmethod
    def for_workspace(cls, workspace_path: str | Path) -> McpServerConfig:
        return cls(workspace_path=Path(workspace_path))
