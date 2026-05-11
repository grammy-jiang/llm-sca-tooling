"""Base contracts for cross-language interface plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field

from llm_sca_tooling.plugins.capability import (
    PluginAvailability,
    PluginCapabilityDescriptor,
)
from llm_sca_tooling.plugins.interface_record import InterfaceRecord, StrictPluginModel
from llm_sca_tooling.storage.registry import RepositoryRecord
from llm_sca_tooling.storage.snapshots import SnapshotRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = [
    "AmbiguousLinkRecord",
    "DetectedInterfaceFile",
    "InterfacePluginBase",
    "PluginConfig",
    "PluginDetectResult",
    "PluginIndexResult",
    "PluginLinkResult",
    "TraversalDirection",
    "TraversalLink",
]


class TraversalDirection(str, Enum):
    outbound = "outbound"
    inbound = "inbound"
    both = "both"


@dataclass(frozen=True)
class PluginConfig:
    options: dict[str, Any] = field(default_factory=dict)


class DetectedInterfaceFile(StrictPluginModel):
    file_path: str
    interface_type_hint: str
    detection_method: str
    confidence: str = "heuristic"


class PluginDetectResult(StrictPluginModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    detected_files: list[DetectedInterfaceFile] = Field(default_factory=list)
    detection_confidence: str = "heuristic"
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    run_stats: dict[str, Any] = Field(default_factory=dict)


class PluginIndexResult(StrictPluginModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    interface_records: list[InterfaceRecord] = Field(default_factory=list)
    generated_artifact_refs: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    run_stats: dict[str, Any] = Field(default_factory=dict)


class AmbiguousLinkRecord(StrictPluginModel):
    interface_id: str
    operation_name: str
    candidate_node_ids: list[str] = Field(default_factory=list)
    reason: str


class PluginLinkResult(StrictPluginModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    nodes_emitted: int = 0
    edges_emitted: int = 0
    interface_records_linked: int = 0
    ambiguous_links: list[AmbiguousLinkRecord] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    run_stats: dict[str, Any] = Field(default_factory=dict)


class TraversalLink(StrictPluginModel):
    from_node_id: str
    to_node_id: str
    via_interface_id: str
    plugin_id: str
    edge_type: str
    confidence: str = "heuristic"
    operation_name: str | None = None
    direction: TraversalDirection = TraversalDirection.both


class InterfacePluginBase(ABC):
    plugin_id: str
    plugin_version: str

    @abstractmethod
    async def check_availability(self) -> PluginAvailability:
        """Return plugin availability without side effects."""

    @abstractmethod
    def describe_capability(self) -> PluginCapabilityDescriptor:
        """Return a stable plugin capability descriptor."""

    @abstractmethod
    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        """Detect candidate interface files."""

    @abstractmethod
    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        """Parse interface files into records without writing graph facts."""

    @abstractmethod
    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        """Write interface nodes and edges to the graph store."""

    @abstractmethod
    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        """Read pre-indexed graph links for a node."""


def repo_files(root: Path) -> list[str]:
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    ]
