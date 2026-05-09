"""Server capability descriptors."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.sampling import SamplingCapabilityRecord
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class ServerCapabilities(StrictBaseModel):
    server_name: str
    server_version: str
    transport: str
    resources: bool = True
    tools: bool = True
    prompts: bool = True
    tasks: bool = True
    subscriptions: bool = True
    sampling: SamplingCapabilityRecord
    limits: JsonObject = Field(default_factory=dict)


def build_capabilities(config: McpServerConfig, sampling: SamplingCapabilityRecord) -> ServerCapabilities:
    return ServerCapabilities(
        server_name=config.server_name,
        server_version=config.server_version,
        transport=config.transport,
        tasks=config.enable_tasks,
        subscriptions=config.resource_subscription_enabled,
        sampling=sampling,
        limits={
            "max_resource_bytes": config.max_resource_bytes,
            "max_graph_slice_nodes": config.max_graph_slice_nodes,
            "max_graph_slice_edges": config.max_graph_slice_edges,
            "task_ttl_seconds_default": config.task_ttl_seconds_default,
            "task_ttl_seconds_max": config.task_ttl_seconds_max,
        },
    )
