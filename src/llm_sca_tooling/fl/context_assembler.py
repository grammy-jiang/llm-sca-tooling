"""Bounded context bundle assembly."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CodeSpan,
    ConfidenceLevel,
    ContextBudget,
    ContextBundle,
    ContextFileEntry,
)
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["assemble_context"]


async def assemble_context(
    workspace: WorkspaceStore,
    issue: IssueText,
    candidates: list[CandidateFile],
    *,
    max_files: int = 8,
) -> ContextBundle:
    selected = candidates[:max_files]
    entries: list[ContextFileEntry] = []
    for candidate in selected:
        graph_slice = await workspace.queries.fetch_by_file(
            candidate.repo_id, candidate.file_path
        )
        spans = _spans(issue, candidate)
        entries.append(
            ContextFileEntry(
                candidate_file=candidate,
                graph_slice={
                    "nodes": [
                        node.model_dump(mode="json") for node in graph_slice.nodes
                    ],
                    "edges": [
                        edge.model_dump(mode="json") for edge in graph_slice.edges
                    ],
                    "source": "graph_slice",
                    "confidence": "parser",
                },
                build_test_evidence=[
                    node.model_dump(mode="json")
                    for node in graph_slice.nodes
                    if node.node_type.value in {"build_target", "test"}
                ],
                exact_spans=spans,
            )
        )
    total_nodes = sum(len(entry.graph_slice.get("nodes", [])) for entry in entries)
    total_edges = sum(len(entry.graph_slice.get("edges", [])) for entry in entries)
    return ContextBundle(
        files=entries,
        total_graph_nodes=total_nodes,
        total_graph_edges=total_edges,
        total_symbol_summaries=0,
        total_sarif_alerts=0,
        budget_used=ContextBudget(
            max_files=max_files,
            actual_files=len(entries),
            actual_graph_nodes=total_nodes,
        ),
        snapshot_ids={
            candidate.repo_id: candidate.snapshot_id for candidate in selected
        },
        is_over_budget=len(candidates) > 10,
    )


def _spans(issue: IssueText, candidate: CandidateFile) -> list[CodeSpan]:
    spans: list[CodeSpan] = []
    for frame in issue.stack_trace_frames:
        if (
            not frame.file_path
            or Path(frame.file_path).name != Path(candidate.file_path).name
        ):
            continue
        line = frame.line or 1
        spans.append(
            CodeSpan(
                file_path=candidate.file_path,
                start_line=line,
                end_line=line,
                content=f"<span {candidate.file_path}:{line}>",
                node_id=candidate.node_id,
                confidence=ConfidenceLevel.heuristic,
                reason="stack_trace_frame",
            )
        )
    return spans
