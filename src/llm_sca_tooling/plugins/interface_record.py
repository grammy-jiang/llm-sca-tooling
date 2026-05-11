"""Cross-language interface record models."""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "GeneratedArtifactRecord",
    "InterfaceKind",
    "InterfaceOperation",
    "InterfaceRecord",
    "OperationParameter",
    "OperationType",
    "make_interface_id",
    "make_operation_id",
]


class StrictPluginModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterfaceKind(str, Enum):
    http = "http"
    websocket = "websocket"
    idl = "idl"
    grpc = "grpc"
    protobuf = "protobuf"
    zeromq = "zeromq"
    mqtt = "mqtt"
    dbus = "dbus"
    custom = "custom"


class OperationType(str, Enum):
    route = "route"
    method = "method"
    event = "event"
    rpc = "rpc"


class OperationParameter(StrictPluginModel):
    name: str
    location: str
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    required: bool = False
    nullable: bool = False


class GeneratedArtifactRecord(StrictPluginModel):
    artifact_id: str
    source_interface_id: str
    generator_tool: str
    file_paths: list[str] = Field(default_factory=list)
    is_checked_in: bool = True
    regeneration_command: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class InterfaceOperation(StrictPluginModel):
    operation_id: str
    interface_id: str
    name: str
    operation_type: OperationType
    http_method: str | None = None
    path_pattern: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    parameters: list[OperationParameter] = Field(default_factory=list)
    status_codes: list[int] | None = None
    auth_hints: list[str] | None = None
    server_handler_node_ids: list[str] = Field(default_factory=list)
    client_callsite_node_ids: list[str] = Field(default_factory=list)
    confidence: str = "heuristic"
    binding_method: str = "heuristic"


class InterfaceRecord(StrictPluginModel):
    interface_id: str
    kind: InterfaceKind
    plugin_id: str
    plugin_version: str
    interface_name: str
    version: str | None = None
    definition_files: list[str] = Field(default_factory=list)
    source_repos: list[str] = Field(default_factory=list)
    operations: list[InterfaceOperation] = Field(default_factory=list)
    generated_artifacts: list[GeneratedArtifactRecord] = Field(default_factory=list)
    confidence: str = "heuristic"
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


def make_interface_id(
    plugin_id: str, kind: InterfaceKind | str, interface_name: str, repo_id: str
) -> str:
    digest = hashlib.sha256(
        "|".join([plugin_id, str(kind), interface_name, repo_id]).encode()
    ).hexdigest()[:16]
    return f"iface:{plugin_id}:{digest}"


def make_operation_id(interface_id: str, name: str, method: str | None = None) -> str:
    digest = hashlib.sha256(
        "|".join([interface_id, name, method or ""]).encode()
    ).hexdigest()[:16]
    return f"ifop:{digest}"
