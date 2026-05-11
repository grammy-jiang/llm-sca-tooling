"""Graph manifest and chunk generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import orjson

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode

__all__ = ["GraphManifestGenerator", "ManifestResult"]


@dataclass
class ManifestResult:
    manifest_id: str
    repo_id: str
    snapshot_id: str
    node_count: int
    edge_count: int
    chunk_artifact_ids: list[str] = field(default_factory=list)
    chunk_paths: list[Path] = field(default_factory=list)
    generated_ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class GraphManifestGenerator:
    """Generate graph manifests and chunk files."""

    def generate(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        repo_id: str,
        snapshot_id: str,
        run_id: str,
        output_dir: Path,
        config: IndexingConfig,
    ) -> ManifestResult:
        manifest_id = (
            "manifest:"
            + hashlib.sha256(f"{repo_id}|{snapshot_id}|{run_id}".encode()).hexdigest()[
                :16
            ]
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        chunk_paths: list[Path] = []
        chunk_ids: list[str] = []

        # Write node chunks
        chunk_size = config.manifest_chunk_size
        for i, chunk_start in enumerate(range(0, len(nodes), chunk_size)):
            node_chunk = nodes[chunk_start : chunk_start + chunk_size]
            chunk_data = [n.model_dump(mode="json") for n in node_chunk]
            chunk_bytes = orjson.dumps(
                {"schema_version": "0.1.0", "type": "nodes", "items": chunk_data}
            )
            chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()[:16]
            chunk_id = f"chunk:nodes:{i}:{chunk_hash}"
            chunk_path = output_dir / f"nodes_chunk_{i:04d}.json"
            chunk_path.write_bytes(chunk_bytes)
            chunk_paths.append(chunk_path)
            chunk_ids.append(chunk_id)

        # Write edge chunks
        for i, chunk_start in enumerate(range(0, len(edges), chunk_size)):
            edge_chunk = edges[chunk_start : chunk_start + chunk_size]
            chunk_data = [e.model_dump(mode="json") for e in edge_chunk]
            chunk_bytes = orjson.dumps(
                {"schema_version": "0.1.0", "type": "edges", "items": chunk_data}
            )
            chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()[:16]
            chunk_id = f"chunk:edges:{i}:{chunk_hash}"
            chunk_path = output_dir / f"edges_chunk_{i:04d}.json"
            chunk_path.write_bytes(chunk_bytes)
            chunk_paths.append(chunk_path)
            chunk_ids.append(chunk_id)

        return ManifestResult(
            manifest_id=manifest_id,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            node_count=len(nodes),
            edge_count=len(edges),
            chunk_artifact_ids=chunk_ids,
            chunk_paths=chunk_paths,
        )
