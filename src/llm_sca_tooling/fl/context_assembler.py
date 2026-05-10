"""Bounded context assembly for localisation results."""

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
from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.summaries import SummaryCache, SymbolSummaryRecord
from llm_sca_tooling.qa.blame import BlameLookup
from llm_sca_tooling.sarif.models import NormalizedAlert
from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.storage.workspace import WorkspaceStore


class BoundedContextAssembler:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def assemble(
        self,
        candidates: list[CandidateFile],
        issue: IssueText,
        *,
        max_files: int = 8,
        max_graph_nodes: int = 2000,
    ) -> ContextBundle:
        budget_max = min(max(max_files, 1), 20)
        selected = candidates[:budget_max]
        entries: list[ContextFileEntry] = []
        graph_generator = GraphSliceGenerator(self.workspace)
        for candidate in selected:
            graph_slice = graph_generator.by_file(
                candidate.repo_id,
                candidate.file_path,
                depth=1,
                limit=max_graph_nodes,
            )
            summaries = _summaries_for_file(
                self.workspace, candidate.repo_id, candidate.file_path
            )
            alerts = [
                alert
                for alert in self.workspace.sarif.get_alerts_for_file(
                    candidate.repo_id, candidate.file_path
                )
                if not alert.suppressed
            ]
            build_test_nodes = _build_test_nodes(self.workspace, candidate)
            blame_entries = (
                BlameLookup(self.workspace)
                .lookup(
                    candidate.repo_id,
                    candidate.file_path,
                    follow_renames=False,
                    depth=3,
                )
                .entries[:3]
            )
            exact_spans = _exact_spans(self.workspace, candidate, issue, alerts)
            entries.append(
                ContextFileEntry(
                    candidate_file=candidate,
                    graph_slice=graph_slice,
                    symbol_summaries=summaries,
                    sarif_alerts=alerts,
                    build_test_evidence=build_test_nodes,
                    blame_entries=blame_entries,
                    exact_spans=exact_spans,
                )
            )
        snapshot_ids = {
            entry.candidate_file.repo_id: entry.candidate_file.snapshot_id
            for entry in entries
            if entry.candidate_file.snapshot_id
        }
        total_nodes = sum(len(entry.graph_slice.nodes) for entry in entries)
        total_edges = sum(len(entry.graph_slice.edges) for entry in entries)
        total_summaries = sum(len(entry.symbol_summaries) for entry in entries)
        total_alerts = sum(len(entry.sarif_alerts) for entry in entries)
        return ContextBundle(
            files=entries,
            total_graph_nodes=total_nodes,
            total_graph_edges=total_edges,
            total_symbol_summaries=total_summaries,
            total_sarif_alerts=total_alerts,
            budget_used=ContextBudget(
                max_files=budget_max,
                actual_files=len(entries),
                max_graph_nodes=max_graph_nodes,
                actual_graph_nodes=total_nodes,
                actual_symbol_summaries=total_summaries,
                token_estimate=_token_estimate(entries),
            ),
            snapshot_ids=snapshot_ids,
            is_over_budget=max_files > 10 or len(candidates) > 10,
        )


def _summaries_for_file(
    workspace: WorkspaceStore, repo_id: str, file_path: str
) -> list[SymbolSummaryRecord]:
    cache = SummaryCache(workspace.storage_root / "summaries")
    summaries: list[SymbolSummaryRecord] = []
    for path in cache.root.glob("summary_*.json"):
        record = SymbolSummaryRecord.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if (
            record.repo_id == repo_id
            and record.file_path == file_path
            and record.invalidated_ts is None
        ):
            summaries.append(record)
    return summaries


def _build_test_nodes(
    workspace: WorkspaceStore, candidate: CandidateFile
) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    for node_type in (
        GraphNodeType.BUILD_TARGET,
        GraphNodeType.TEST,
        GraphNodeType.GENERATED_TEST,
    ):
        nodes.extend(workspace.graph.fetch_nodes_by_type(candidate.repo_id, node_type))
    return [
        node
        for node in nodes
        if node.file_path == candidate.file_path
        or str(node.properties.get("file_path") or "") == candidate.file_path
    ]


def _exact_spans(
    workspace: WorkspaceStore,
    candidate: CandidateFile,
    issue: IssueText,
    alerts: list[NormalizedAlert],
) -> list[CodeSpan]:
    lines: list[tuple[int, str]] = []
    for frame in issue.stack_trace_frames:
        if (
            frame.file_path
            and _path_matches(frame.file_path, candidate.file_path)
            and frame.line
        ):
            lines.append((frame.line, "stack_trace_frame"))
    for alert in alerts:
        if alert.start_line:
            lines.append((alert.start_line, "sarif_alert"))
    result: list[CodeSpan] = []
    seen: set[tuple[int, str]] = set()
    for line_no, reason in lines:
        key = (line_no, reason)
        if key in seen:
            continue
        seen.add(key)
        span = _read_span(workspace, candidate, line_no, reason)
        if span is not None:
            result.append(span)
    return result


def _read_span(
    workspace: WorkspaceStore, candidate: CandidateFile, line_no: int, reason: str
) -> CodeSpan | None:
    repo = workspace.repositories.get_repo(candidate.repo_id)
    path = Path(repo.root_path) / candidate.file_path
    if not path.exists() or not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    start = max(1, line_no - 4)
    end = min(len(lines), start + 9)
    if start > end:
        return None
    content = "\n".join(lines[start - 1 : end])
    return CodeSpan(
        file_path=candidate.file_path,
        start_line=start,
        end_line=end,
        content=content,
        node_id=candidate.node_id,
        confidence=ConfidenceLevel.HEURISTIC,
        reason=reason,
    )


def _path_matches(left: str, right: str) -> bool:
    normalized = left.strip("/").replace("\\", "/")
    return (
        normalized == right or right.endswith(normalized) or normalized.endswith(right)
    )


def _token_estimate(entries: list[ContextFileEntry]) -> int:
    text: list[str] = []
    for entry in entries:
        text.extend(summary.summary_text for summary in entry.symbol_summaries)
        text.extend(span.content for span in entry.exact_spans)
        text.extend(alert.message for alert in entry.sarif_alerts)
    total = sum(len(item.split()) for item in text)
    return max(0, total)
