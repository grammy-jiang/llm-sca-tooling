"""Bind normalized SARIF alerts to graph file and symbol nodes."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.sarif.models import NormalizedAlert, NormalizedSarifRun
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.storage.workspace import WorkspaceStore


class BindingDiagnostic(StrictBaseModel):
    code: str
    message: str
    alert_id: str | None = None
    file_path: str | None = None


class BindingResult(StrictBaseModel):
    run: NormalizedSarifRun
    diagnostics: list[BindingDiagnostic] = Field(default_factory=list)
    bound_alert_count: int = 0
    symbol_bound_alert_count: int = 0


class AlertBinder:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def bind_run(self, run: NormalizedSarifRun) -> BindingResult:
        diagnostics: list[BindingDiagnostic] = []
        bound_alerts: list[NormalizedAlert] = []
        bound_count = 0
        symbol_count = 0
        for alert in run.alerts:
            bound, alert_diags = self.bind_alert(run, alert)
            diagnostics.extend(alert_diags)
            if bound.bound_file_node_id:
                bound_count += 1
            if bound.bound_symbol_node_ids:
                symbol_count += 1
            bound_alerts.append(bound)
        bound_run = run.model_copy(update={"alerts": bound_alerts}, deep=True)
        return BindingResult(
            run=bound_run,
            diagnostics=diagnostics,
            bound_alert_count=bound_count,
            symbol_bound_alert_count=symbol_count,
        )

    def bind_alert(
        self, run: NormalizedSarifRun, alert: NormalizedAlert
    ) -> tuple[NormalizedAlert, list[BindingDiagnostic]]:
        diagnostics: list[BindingDiagnostic] = []
        if not alert.file_path:
            return alert.model_copy(update={"binding_confidence": "none"}, deep=True), [
                BindingDiagnostic(
                    code="SARIF_UNRESOLVABLE_LOCATION",
                    message="alert has no repo-relative file path",
                    alert_id=alert.alert_id,
                )
            ]
        graph_slice = self.workspace.graph.fetch_by_file(
            run.repo_id, alert.file_path, snapshot_id=run.snapshot_id
        )
        nodes = list(graph_slice.nodes)
        if not nodes:
            graph_slice = self.workspace.graph.fetch_by_file(
                run.repo_id, alert.file_path
            )
            nodes = list(graph_slice.nodes)
        file_nodes = [
            node
            for node in nodes
            if node.node_type == GraphNodeType.FILE
            and node.file_path == alert.file_path
        ]
        if not file_nodes:
            return alert.model_copy(update={"binding_confidence": "none"}, deep=True), [
                BindingDiagnostic(
                    code="SARIF_FILE_NODE_NOT_FOUND",
                    message="no graph file node matches alert path",
                    alert_id=alert.alert_id,
                    file_path=alert.file_path,
                )
            ]
        file_node = sorted(file_nodes, key=lambda node: node.created_ts)[-1]
        symbol_nodes = [
            node
            for node in self.workspace.graph.find_symbols(
                run.repo_id, file_path=alert.file_path, snapshot_id=run.snapshot_id
            )
            if _overlaps(node.span, alert.start_line, alert.end_line)
        ]
        if not symbol_nodes:
            symbol_nodes = [
                node
                for node in self.workspace.graph.find_symbols(
                    run.repo_id, file_path=alert.file_path
                )
                if _overlaps(node.span, alert.start_line, alert.end_line)
            ]
        symbol_nodes = sorted(
            symbol_nodes,
            key=lambda node: (
                _full_contains(node.span, alert.start_line, alert.end_line) is False,
                (node.span.end_line - node.span.start_line) if node.span else 999999,
                node.node_id,
            ),
        )
        confidence = (
            "parser"
            if symbol_nodes
            and _full_contains(symbol_nodes[0].span, alert.start_line, alert.end_line)
            else "heuristic"
        )
        if not symbol_nodes and alert.start_line is None:
            confidence = "heuristic"
        if (
            file_node.snapshot.git_sha != run.git_sha
            or file_node.snapshot.worktree_snapshot_id != run.worktree_snapshot_id
        ):
            diagnostics.append(
                BindingDiagnostic(
                    code="SARIF_MIXED_SNAPSHOT_BINDING",
                    message="alert run snapshot differs from bound graph node snapshot",
                    alert_id=alert.alert_id,
                    file_path=alert.file_path,
                )
            )
        return (
            alert.model_copy(
                update={
                    "bound_file_node_id": file_node.node_id,
                    "bound_symbol_node_ids": [node.node_id for node in symbol_nodes],
                    "binding_confidence": confidence,
                    "properties": {
                        **alert.properties,
                        "mixed_snapshot_binding": bool(diagnostics),
                    },
                },
                deep=True,
            ),
            diagnostics,
        )


def _overlaps(span, start_line: int | None, end_line: int | None) -> bool:
    if span is None or start_line is None:
        return False
    end = end_line or start_line
    return span.start_line <= end and span.end_line >= start_line


def _full_contains(span, start_line: int | None, end_line: int | None) -> bool:
    if span is None or start_line is None:
        return False
    end = end_line or start_line
    return span.start_line <= start_line and span.end_line >= end
