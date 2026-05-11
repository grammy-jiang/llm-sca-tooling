"""Keyword retrieval against graph nodes."""

from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy import text

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["keyword_retrieve"]

_STOP = {"the", "and", "or", "to", "in", "a", "of", "when", "is", "it", "on"}


async def keyword_retrieve(
    workspace: WorkspaceStore, issue: IssueText, repos: list[str] | None = None
) -> list[CandidateFile]:
    nodes = await _nodes(workspace, repos)
    terms = _terms(issue)
    if not terms:
        return []
    doc_terms = {node.node_id: Counter(_tokens(_search_text(node))) for node in nodes}
    df = Counter(term for counts in doc_terms.values() for term in counts)
    scored: dict[tuple[str, str], tuple[float, GraphNode, list[str]]] = {}
    for node in nodes:
        if not node.file_path:
            continue
        counts = doc_terms[node.node_id]
        score = 0.0
        matched: list[str] = []
        for term in terms:
            if counts[term] == 0:
                continue
            matched.append(term)
            score += counts[term] * math.log((len(nodes) + 1) / (df[term] + 1) + 1)
        if node.file_path in issue.mentioned_files:
            score += 2.0
            matched.append("exact_file")
        if (node.qualified_name or node.label) in issue.mentioned_symbols:
            score += 1.5
            matched.append("exact_symbol")
        if score <= 0:
            continue
        key = (node.repo.repo_id, node.file_path)
        old = scored.get(key)
        if old is None or score > old[0]:
            scored[key] = (score, node, matched)
    max_score = max((item[0] for item in scored.values()), default=1.0)
    return [
        _candidate(node, min(score / max_score, 1.0), matched)
        for score, node, matched in sorted(
            scored.values(), key=lambda item: item[0], reverse=True
        )
    ]


def _candidate(node: GraphNode, score: float, matched: list[str]) -> CandidateFile:
    signal = CandidateSignal(
        signal_type=SignalType.keyword,
        raw_score=score,
        weight=0.25,
        weighted_score=score * 0.25,
        evidence=f"keyword terms matched: {', '.join(sorted(set(matched)))}",
        source_refs=[node.node_id],
        confidence=ConfidenceLevel.analyser,
    )
    snapshot_id = node.snapshot.worktree_snapshot_id or node.snapshot.git_sha
    return CandidateFile(
        candidate_id=candidate_id(node.repo.repo_id, node.file_path or ""),
        file_path=node.file_path or "",
        repo_id=node.repo.repo_id,
        node_id=node.node_id,
        signals=[signal],
        combined_score=score,
        confidence=ConfidenceLevel.analyser,
        evidence_summary=signal.evidence,
        snapshot_id=snapshot_id or node.snapshot.repo_id,
    )


def _terms(issue: IssueText) -> list[str]:
    raw = [
        *issue.mentioned_files,
        *issue.mentioned_symbols,
        *(frame.function_name or "" for frame in issue.stack_trace_frames),
        *(frame.file_path or "" for frame in issue.stack_trace_frames),
        *issue.error_strings,
        issue.normalized_text,
    ]
    return sorted(
        {token for item in raw for token in _tokens(item) if token not in _STOP}
    )


def _tokens(text_value: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text_value)]
    return [token[:-3] if token.endswith("ing") else token for token in tokens]


def _search_text(node: GraphNode) -> str:
    return " ".join(
        str(part or "")
        for part in [node.label, node.qualified_name, node.file_path, node.properties]
    )


async def _nodes(workspace: WorkspaceStore, repos: list[str] | None) -> list[GraphNode]:
    async with workspace._session_factory() as session:
        rows = (
            await session.execute(text("SELECT payload_json FROM graph_nodes"))
        ).all()
    nodes = [GraphNode.model_validate_json(str(row[0])) for row in rows]
    return [node for node in nodes if not repos or node.repo.repo_id in repos]
