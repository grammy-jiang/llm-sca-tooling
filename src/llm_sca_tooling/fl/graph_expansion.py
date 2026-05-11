"""Graph-neighbour expansion for candidate files."""

from __future__ import annotations

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["expand_graph_neighbours"]


async def expand_graph_neighbours(
    workspace: WorkspaceStore,
    candidates: list[CandidateFile],
    *,
    max_hops: int = 2,
    max_expansion_files: int = 20,
    decay: float = 0.6,
) -> list[CandidateFile]:
    expanded: list[CandidateFile] = []
    seen = {(candidate.repo_id, candidate.file_path) for candidate in candidates}
    for candidate in candidates:
        seeds = await workspace.queries.fetch_by_file(
            candidate.repo_id, candidate.file_path
        )
        frontier = [node.node_id for node in seeds.nodes]
        for hop in range(1, max_hops + 1):
            next_frontier: list[str] = []
            for node_id in frontier:
                graph_slice = await workspace.queries.fetch_neighbours(node_id)
                for node in graph_slice.nodes:
                    if (
                        not node.file_path
                        or (node.repo.repo_id, node.file_path) in seen
                    ):
                        continue
                    seen.add((node.repo.repo_id, node.file_path))
                    next_frontier.append(node.node_id)
                    expanded.append(
                        _expanded(candidate, node.file_path, node.node_id, decay**hop)
                    )
                    if len(expanded) >= max_expansion_files:
                        return expanded
            frontier = next_frontier
    return expanded


def _expanded(
    source: CandidateFile, file_path: str, node_id: str, multiplier: float
) -> CandidateFile:
    score = min(source.combined_score * multiplier, 1.0)
    signal = CandidateSignal(
        signal_type=SignalType.graph_neighbour,
        raw_score=score,
        weight=0.1,
        weighted_score=score * 0.1,
        evidence=f"graph neighbour of {source.file_path}",
        source_refs=[source.node_id, node_id],
        confidence=ConfidenceLevel.parser,
    )
    return CandidateFile(
        candidate_id=candidate_id(source.repo_id, file_path, "graph"),
        file_path=file_path,
        repo_id=source.repo_id,
        node_id=node_id,
        signals=[signal],
        combined_score=score,
        confidence=ConfidenceLevel.parser,
        evidence_summary=signal.evidence,
        snapshot_id=source.snapshot_id,
    )
