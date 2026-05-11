"""Capability descriptors for interface plugins."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.plugins.interface_record import InterfaceKind, StrictPluginModel

__all__ = ["PluginAvailability", "PluginCapabilityDescriptor"]


class PluginAvailability(StrictPluginModel):
    plugin_id: str
    available: bool
    missing_deps: list[str] = Field(default_factory=list)
    tool_paths: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PluginCapabilityDescriptor(StrictPluginModel):
    plugin_id: str
    plugin_version: str
    interface_kinds: list[InterfaceKind]
    supported_server_languages: list[str] = Field(default_factory=list)
    supported_client_languages: list[str] = Field(default_factory=list)
    emitted_node_types: list[str] = Field(default_factory=list)
    emitted_edge_types: list[str] = Field(default_factory=list)
    max_confidence: str = "heuristic"
    requires_external_tools: list[str] = Field(default_factory=list)
    requires_build_artifacts: bool = False
    incremental_support: bool = False
