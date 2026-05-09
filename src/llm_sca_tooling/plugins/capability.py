"""Plugin capability and availability models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType


class InterfaceKind(StrEnum):
    HTTP = "http"
    WEBSOCKET = "websocket"
    IDL = "idl"
    GRPC = "grpc"
    PROTOBUF = "protobuf"
    ZEROMQ = "zeromq"
    MQTT = "mqtt"
    DBUS = "dbus"
    CUSTOM = "custom"


class OperationType(StrEnum):
    ROUTE = "route"
    METHOD = "method"
    EVENT = "event"
    RPC = "rpc"


class ConfidenceLevel(StrEnum):
    HEURISTIC = "heuristic"
    ANALYSER = "analyser"
    PARSER = "parser"


CONFIDENCE_RANK = {
    ConfidenceLevel.HEURISTIC: 1,
    ConfidenceLevel.ANALYSER: 2,
    ConfidenceLevel.PARSER: 3,
}


CONFIDENCE_VALUE = {
    ConfidenceLevel.HEURISTIC: 0.45,
    ConfidenceLevel.ANALYSER: 0.75,
    ConfidenceLevel.PARSER: 0.95,
}


class TraversalDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"


class PluginAvailability(StrictBaseModel):
    plugin_id: str
    available: bool
    missing_deps: list[str] = Field(default_factory=list)
    tool_paths: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PluginCapabilityDescriptor(StrictBaseModel):
    plugin_id: str
    plugin_version: str
    interface_kinds: list[InterfaceKind] = Field(default_factory=list)
    supported_server_languages: list[str] = Field(default_factory=list)
    supported_client_languages: list[str] = Field(default_factory=list)
    emitted_node_types: list[GraphNodeType] = Field(default_factory=list)
    emitted_edge_types: list[GraphEdgeType] = Field(default_factory=list)
    max_confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    requires_external_tools: list[str] = Field(default_factory=list)
    requires_build_artifacts: bool = False
    incremental_support: bool = False
