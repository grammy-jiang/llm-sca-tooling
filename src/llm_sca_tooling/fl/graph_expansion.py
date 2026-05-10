"""Graph-neighbour expansion for Phase 9 candidates."""

from __future__ import annotations

from collections import deque

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
)
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.storage.graph_store import GraphStore
from llm_sca_tooling.storage.ids import snapshot_id_for

_EXPANSION_EDGES = {
    GraphEdgeType.CALLS,
    GraphEdgeType.IMPORTS,
    GraphEdgeType.TESTS,
    GraphEdgeType.DOCUMENTS,
    GraphEdgeType.DATAFLOW,
    GraphEdgeType.WARNED_BY,
    GraphEdgeType.EXPOSES,
    GraphEdgeType.CONSUMES,
    GraphEdgeType.FFI,
    GraphEdgeType.IMPLEMENTS,
}


class GraphNeighbourExpander:
    def __init__(self, graph: GraphStore) -> None:
        self.graph = graph

    def expand(
        self,
        candidates: list[CandidateFile],
        *,
        max_hops: int = 2,
        max_expansion_files: int = 20,
        decay: float = 0.6,
    ) -> list[CandidateFile]:
        expanded: dict[tuple[str, str], CandidateFile] = {}
        source_keys = {
            (candidate.repo_id, candidate.file_path) for candidate in candidates
        }
        for candidate in candidates:
            for node in self.graph.fetch_by_file(
                candidate.repo_id, candidate.file_path
            ).nodes:
                for target, edge, hop in self._walk(node, max_hops=max_hops):
                    if not target.file_path:
                        continue
                    key = (target.repo.repo_id, target.file_path)
                    if key in source_keys:
                        continue
                    base_score = candidate.combined_score or _best_signal_score(
                        candidate
                    )
                    raw_score = min(1.0, base_score * (decay**hop))
                    if bool(target.properties.get("is_generated", False)):
                        raw_score *= 0.5
                    confidence = (
                        ConfidenceLevel.PARSER
                        if edge.edge_type == GraphEdgeType.WARNED_BY
                        else ConfidenceLevel.HEURISTIC
                    )
                    signal = CandidateSignal(
                        signal_type=SignalType.GRAPH_NEIGHBOUR,
                        raw_score=raw_score,
                        evidence=f"{edge.edge_type.value} hop-{hop} expansion from {candidate.file_path}",
                        source_refs=[candidate.node_id, edge.edge_id, target.node_id],
                        confidence=confidence,
                    )
                    expanded_candidate = CandidateFile(
                        candidate_id=f"candidate:file:graph:{target.repo.repo_id}:{target.file_path}",
                        file_path=target.file_path,
                        repo_id=target.repo.repo_id,
                        node_id=target.node_id,
                        signals=[signal],
                        combined_score=raw_score,
                        confidence=confidence,
                        evidence_summary=signal.evidence,
                        snapshot_id=snapshot_id_for(target.snapshot),
                        is_generated=bool(target.properties.get("is_generated", False)),
                    )
                    existing = expanded.get(key)
                    if (
                        existing is None
                        or expanded_candidate.combined_score > existing.combined_score
                    ):
                        expanded[key] = expanded_candidate
        return sorted(
            expanded.values(),
            key=lambda item: item.combined_score,
            reverse=True,
        )[:max_expansion_files]

    def _walk(
        self, start: GraphNode, *, max_hops: int
    ) -> list[tuple[GraphNode, GraphEdge, int]]:
        results: list[tuple[GraphNode, GraphEdge, int]] = []
        queue: deque[tuple[str, int]] = deque([(start.node_id, 0)])
        seen = {start.node_id}
        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_hops:
                continue
            edges = self._adjacent_edges(node_id)
            for edge in edges:
                if edge.edge_type not in _EXPANSION_EDGES:
                    continue
                other_id = (
                    edge.target_id if edge.source_id == node_id else edge.source_id
                )
                if other_id in seen:
                    continue
                seen.add(other_id)
                target = self.graph.fetch_node(other_id)
                if target is None:
                    continue
                hop = depth + 1
                results.append((target, edge, hop))
                queue.append((target.node_id, hop))
        return results

    def _adjacent_edges(self, node_id: str) -> list[GraphEdge]:
        rows = self.graph.conn.execute(
            "SELECT payload_json FROM graph_edges WHERE source_id=? OR target_id=?",
            (node_id, node_id),
        ).fetchall()
        return [GraphEdge.model_validate_json(row["payload_json"]) for row in rows]


def _best_signal_score(candidate: CandidateFile) -> float:
    if not candidate.signals:
        return candidate.combined_score
    return max(signal.raw_score for signal in candidate.signals)
