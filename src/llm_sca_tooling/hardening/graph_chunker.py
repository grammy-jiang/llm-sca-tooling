"""Large-graph chunker for lazy loading and streaming.

``GraphChunker`` splits a graph manifest into topology-aware chunks so
that large graphs do not exhaust memory or overflow resource responses.
Chunks follow module/package topology; they are stored as artefact
references and served on demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["ChunkManifest", "GraphChunk", "GraphChunker"]

logger = get_logger(__name__)

_DEFAULT_MAX_CHUNK_NODES = 2000


@dataclass
class GraphChunk:
    chunk_id: str
    chunk_index: int
    nodes: list[str]
    artefact_id: str | None = None


@dataclass
class ChunkManifest:
    repo_id: str
    git_sha: str
    total_nodes: int
    chunk_count: int
    chunks: list[GraphChunk] = field(default_factory=list)


class GraphChunker:
    """Split a graph into topology-aware chunks.

    Args:
        max_chunk_nodes: Maximum nodes per chunk (default 2000).
        artefact_registry: Optional callable to store chunk artefacts.
            Called with ``(chunk_id, chunk_data)`` and must return an
            ``artefact_id`` string.
    """

    def __init__(
        self,
        max_chunk_nodes: int = _DEFAULT_MAX_CHUNK_NODES,
        artefact_registry: Any | None = None,
    ) -> None:
        self._max_chunk_nodes = max_chunk_nodes
        self._artefact_registry = artefact_registry
        self._chunks: dict[str, GraphChunk] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(
        self,
        repo_id: str,
        git_sha: str,
        nodes: list[str],
        edges: list[tuple[str, str]] | None = None,
    ) -> ChunkManifest:
        """Partition *nodes* into module-topology chunks.

        Nodes are grouped by their dotted-path prefix (module/package).
        If a group exceeds ``max_chunk_nodes`` it is further split.

        Returns a ``ChunkManifest`` with ``artefact_id`` references for
        each chunk.
        """
        groups = self._group_by_module(nodes)
        raw_chunks = self._split_groups(groups)

        manifest_chunks: list[GraphChunk] = []
        for i, chunk_nodes in enumerate(raw_chunks):
            chunk_id = f"chunk:{repo_id}:{git_sha[:8]}:{i}"
            artefact_id: str | None = None
            if self._artefact_registry is not None:
                chunk_data = {
                    "chunk_id": chunk_id,
                    "repo_id": repo_id,
                    "git_sha": git_sha,
                    "chunk_index": i,
                    "nodes": chunk_nodes,
                }
                artefact_id = self._artefact_registry(chunk_id, chunk_data)
            chunk = GraphChunk(
                chunk_id=chunk_id,
                chunk_index=i,
                nodes=chunk_nodes,
                artefact_id=artefact_id,
            )
            self._chunks[chunk_id] = chunk
            manifest_chunks.append(chunk)

        manifest = ChunkManifest(
            repo_id=repo_id,
            git_sha=git_sha,
            total_nodes=len(nodes),
            chunk_count=len(manifest_chunks),
            chunks=manifest_chunks,
        )
        logger.info(
            "Chunked graph: repo=%s nodes=%d chunks=%d",
            repo_id,
            len(nodes),
            len(manifest_chunks),
        )
        return manifest

    def get_chunk(self, chunk_id: str) -> GraphChunk | None:
        """Return the chunk with *chunk_id*, or ``None`` if not found."""
        return self._chunks.get(chunk_id)

    def get_chunks_for_nodes(self, node_ids: list[str]) -> list[GraphChunk]:
        """Return all chunks that contain at least one node in *node_ids*."""
        node_set = set(node_ids)
        return [c for c in self._chunks.values() if node_set.intersection(c.nodes)]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _group_by_module(self, nodes: list[str]) -> dict[str, list[str]]:
        """Group node IDs by their top-level module prefix."""
        groups: dict[str, list[str]] = {}
        for node in nodes:
            prefix = node.split(".")[0] if "." in node else node.split("/")[0]
            groups.setdefault(prefix, []).append(node)
        return groups

    def _split_groups(self, groups: dict[str, list[str]]) -> list[list[str]]:
        """Split groups into chunks respecting ``max_chunk_nodes``."""
        chunks: list[list[str]] = []
        current: list[str] = []
        for group_nodes in groups.values():
            for i in range(0, max(len(group_nodes), 1), self._max_chunk_nodes):
                batch = group_nodes[i : i + self._max_chunk_nodes]
                if len(current) + len(batch) > self._max_chunk_nodes:
                    if current:
                        chunks.append(current)
                    current = list(batch)
                else:
                    current.extend(batch)
        if current:
            chunks.append(current)
        return chunks or [[]]
