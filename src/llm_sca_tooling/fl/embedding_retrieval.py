"""Semantic embedding retrieval against graph nodes (Phase 9 activation).

Parallel signal stream to keyword retrieval: embeds the normalized issue text
and node search texts, scores by cosine similarity, and emits ``EMBEDDING``
signals for the ranking merge. Unavailable adapters yield an empty stream —
the localisation pipeline records the signal as missing instead of failing.
"""

from __future__ import annotations

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingInterface,
    EmbeddingUnavailable,
)
from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.keyword_retrieval import _nodes, _search_text
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)
from llm_sca_tooling.fl.ranking import DEFAULT_SIGNAL_WEIGHTS
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["embedding_retrieve"]

_EMBEDDING_WEIGHT = DEFAULT_SIGNAL_WEIGHTS[SignalType.embedding]
# Similarity below this is noise, not evidence — drop the candidate.
_MIN_SIMILARITY = 0.1


async def embedding_retrieve(
    workspace: WorkspaceStore,
    issue: IssueText,
    adapter: EmbeddingInterface,
    repos: list[str] | None = None,
    *,
    max_candidates: int = 20,
) -> list[CandidateFile]:
    """Rank files by semantic similarity between issue text and node text."""
    if not adapter.is_available():
        return []
    nodes = [
        node for node in await _nodes(workspace, repos) if node.file_path is not None
    ]
    if not nodes or not issue.normalized_text.strip():
        return []

    try:
        query = adapter.embed_text(issue.normalized_text, context_hint="issue")
        corpus = adapter.embed_batch([_search_text(node) for node in nodes])
    except EmbeddingUnavailable:
        return []

    # Best-scoring node per file, mirroring keyword retrieval's dedup.
    best: dict[tuple[str, str], tuple[float, GraphNode]] = {}
    for node, vector in zip(nodes, corpus, strict=True):
        score = max(0.0, min(1.0, adapter.similarity(query, vector)))
        if score < _MIN_SIMILARITY:
            continue
        key = (node.repo.repo_id, str(node.file_path))
        old = best.get(key)
        if old is None or score > old[0]:
            best[key] = (score, node)

    ranked = sorted(best.values(), key=lambda item: item[0], reverse=True)
    return [_candidate(node, score) for score, node in ranked[:max_candidates]]


def _candidate(node: GraphNode, score: float) -> CandidateFile:
    signal = CandidateSignal(
        signal_type=SignalType.embedding,
        raw_score=score,
        weight=_EMBEDDING_WEIGHT,
        weighted_score=score * _EMBEDDING_WEIGHT,
        evidence=f"semantic similarity {score:.2f} to issue text",
        source_refs=[node.node_id],
        confidence=ConfidenceLevel.heuristic,
    )
    snapshot_id = node.snapshot.worktree_snapshot_id or node.snapshot.git_sha
    return CandidateFile(
        candidate_id=candidate_id(node.repo.repo_id, str(node.file_path)),
        file_path=str(node.file_path),
        repo_id=node.repo.repo_id,
        node_id=node.node_id,
        signals=[signal],
        combined_score=score,
        confidence=ConfidenceLevel.heuristic,
        evidence_summary=signal.evidence,
        snapshot_id=snapshot_id or node.snapshot.repo_id,
    )
