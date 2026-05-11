"""Basic graph export and import.

Exports graph slices as JSON bundles for test fixtures, cross-tool sharing,
and operational review.  Imports validate Phase 1 schema models before insert.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.schemas.base import SCHEMA_VERSION
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.storage.errors import ImportExportError
from llm_sca_tooling.storage.graph_queries import GraphSlice
from llm_sca_tooling.storage.graph_store import GraphStore
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["ExportImportService", "ExportBundle", "ImportResult"]

logger = get_logger(__name__)


@dataclass
class ExportBundle:
    export_id: str
    export_type: str
    created_ts: str
    schema_version: str
    repos: list[dict[str, Any]]
    snapshots: list[dict[str, Any]]
    payload: dict[str, Any]
    artifact_refs: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    imported_nodes: int = 0
    imported_edges: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class ExportImportService:
    """Export graph slices and import them into an empty or existing store."""

    def __init__(self, graph_store: GraphStore) -> None:
        self._graph = graph_store

    def export_slice(self, slice: GraphSlice) -> ExportBundle:
        """Serialize a graph slice to an ExportBundle."""
        return ExportBundle(
            export_id=f"export:{uuid.uuid4().hex[:16]}",
            export_type="graph_slice",
            created_ts=datetime.now(UTC).isoformat(),
            schema_version=SCHEMA_VERSION,
            repos=[{"repo_id": slice.repo_id}],
            snapshots=[{"snapshot_id": s} for s in slice.snapshot_ids],
            payload={
                "nodes": [n.model_dump(mode="json") for n in slice.nodes],
                "edges": [e.model_dump(mode="json") for e in slice.edges],
                "snapshot_consistency": slice.snapshot_consistency,
            },
            diagnostics=(
                [] if not slice.truncated else [f"Truncated at {slice.limit} nodes"]
            ),
        )

    def save_bundle(self, bundle: ExportBundle, path: Path) -> None:
        """Write an ExportBundle to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "export_id": bundle.export_id,
            "export_type": bundle.export_type,
            "created_ts": bundle.created_ts,
            "schema_version": bundle.schema_version,
            "repos": bundle.repos,
            "snapshots": bundle.snapshots,
            "payload": bundle.payload,
            "artifact_refs": bundle.artifact_refs,
            "diagnostics": bundle.diagnostics,
        }
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def load_bundle(self, path: Path) -> ExportBundle:
        """Read an ExportBundle from a JSON file."""
        if not path.exists():
            raise ImportExportError(f"Bundle file not found: {path}")
        raw = orjson.loads(path.read_bytes())
        version = raw.get("schema_version", "unknown")
        if version != SCHEMA_VERSION:
            raise ImportExportError(
                f"Bundle schema version {version!r} != current {SCHEMA_VERSION!r}"
            )
        return ExportBundle(
            export_id=raw["export_id"],
            export_type=raw["export_type"],
            created_ts=raw["created_ts"],
            schema_version=version,
            repos=raw.get("repos", []),
            snapshots=raw.get("snapshots", []),
            payload=raw.get("payload", {}),
            artifact_refs=raw.get("artifact_refs", []),
            diagnostics=raw.get("diagnostics", []),
        )

    async def import_bundle(self, bundle: ExportBundle) -> ImportResult:
        """Validate and insert bundle contents into the graph store."""
        result = ImportResult()
        payload = bundle.payload

        # Validate nodes
        raw_nodes = payload.get("nodes", [])
        valid_nodes: list[GraphNode] = []
        for raw in raw_nodes:
            try:
                valid_nodes.append(GraphNode.model_validate(raw))
            except Exception as exc:
                result.errors.append(f"Invalid node payload: {exc}")

        # Validate edges
        raw_edges = payload.get("edges", [])
        valid_edges: list[GraphEdge] = []
        for raw in raw_edges:
            try:
                valid_edges.append(GraphEdge.model_validate(raw))
            except Exception as exc:
                result.errors.append(f"Invalid edge payload: {exc}")

        if result.errors:
            raise ImportExportError(
                f"Bundle validation failed with {len(result.errors)} error(s): "
                + "; ".join(result.errors[:3])
            )

        # Import nodes
        node_result = await self._graph.add_nodes(valid_nodes)
        result.imported_nodes = node_result.written
        result.skipped += node_result.skipped

        # Import edges
        edge_result = await self._graph.add_edges(valid_edges)
        result.imported_edges = edge_result.written
        result.skipped += edge_result.skipped

        return result
