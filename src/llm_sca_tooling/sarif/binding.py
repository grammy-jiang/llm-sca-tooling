"""Bind normalized SARIF alerts to graph file and symbol nodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm_sca_tooling.sarif.models import NormalizedAlert, NormalizedSarifRun
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["BindingDiagnostic", "bind_sarif_run"]

_SYMBOL_TYPES = {
    GraphNodeType.class_,
    GraphNodeType.function,
    GraphNodeType.method,
    GraphNodeType.variable,
}


@dataclass(frozen=True)
class BindingDiagnostic:
    code: str
    message: str
    alert_id: str
    file_path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "alert_id": self.alert_id,
            "file_path": self.file_path,
        }


@dataclass
class BindingResult:
    run: NormalizedSarifRun
    diagnostics: list[BindingDiagnostic] = field(default_factory=list)


async def bind_sarif_run(
    workspace: WorkspaceStore, run: NormalizedSarifRun
) -> BindingResult:
    diagnostics: list[BindingDiagnostic] = []
    bound_alerts: list[NormalizedAlert] = []
    for alert in run.alerts:
        bound, alert_diagnostics = await _bind_alert(workspace, run, alert)
        bound_alerts.append(bound)
        diagnostics.extend(alert_diagnostics)
    return BindingResult(
        run=run.model_copy(update={"alerts": bound_alerts}),
        diagnostics=diagnostics,
    )


async def _bind_alert(
    workspace: WorkspaceStore, run: NormalizedSarifRun, alert: NormalizedAlert
) -> tuple[NormalizedAlert, list[BindingDiagnostic]]:
    if not alert.file_path:
        return alert, [
            BindingDiagnostic(
                code="SARIF_UNRESOLVABLE_LOCATION",
                message="alert has no resolvable file path",
                alert_id=alert.alert_id,
            )
        ]
    graph_slice = await workspace.queries.fetch_by_file(run.repo_id, alert.file_path)
    file_node = next(
        (
            node
            for node in graph_slice.nodes
            if node.node_type in {GraphNodeType.file, GraphNodeType.module}
        ),
        None,
    )
    if file_node is None:
        return alert, [
            BindingDiagnostic(
                code="SARIF_FILE_NODE_NOT_FOUND",
                message="alert file has no graph file node",
                alert_id=alert.alert_id,
                file_path=alert.file_path,
            )
        ]
    symbols = [
        node
        for node in graph_slice.nodes
        if node.node_type in _SYMBOL_TYPES and _overlaps(node, alert)
    ]
    confidence = "parser" if symbols and _contains(symbols[0], alert) else "heuristic"
    properties = dict(alert.properties)
    if file_node.snapshot.git_sha != run.git_sha:
        properties["mixed_snapshot_binding"] = True
        confidence = "heuristic"
    if alert.suppressed:
        properties["suppressed"] = True
    return (
        alert.model_copy(
            update={
                "bound_file_node_id": file_node.node_id,
                "bound_symbol_node_ids": [node.node_id for node in symbols],
                "binding_confidence": confidence,
                "properties": properties,
            }
        ),
        [],
    )


def _overlaps(node: GraphNode, alert: NormalizedAlert) -> bool:
    if node.span is None or alert.start_line is None:
        return False
    alert_end = alert.end_line or alert.start_line
    return (
        node.span.start_line <= alert_end
        and (node.span.end_line or node.span.start_line) >= alert.start_line
    )


def _contains(node: GraphNode, alert: NormalizedAlert) -> bool:
    if node.span is None or alert.start_line is None:
        return False
    alert_end = alert.end_line or alert.start_line
    return (
        node.span.start_line <= alert.start_line
        and (node.span.end_line or node.span.start_line) >= alert_end
    )
