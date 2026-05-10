"""Alert binding to graph nodes for Phase 12 SAST repair."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertSpan,
    BindingConfidence,
)


def bind_alert(
    *,
    alert: dict[str, Any],
    graph_snapshot_id: str | None = None,
    sarif_snapshot_id: str | None = None,
    file_node_lookup: dict[str, str] | None = None,
    symbol_lookup: dict[tuple[str, int], list[str]] | None = None,
) -> AlertBinding:
    """Map a SARIF alert (dict form) to an :class:`AlertBinding`.

    The lookups are pure, in-memory mappings supplied by the caller so this
    function stays deterministic and side-effect free. ``file_node_lookup`` maps
    repo-relative file paths to graph file-node IDs. ``symbol_lookup`` maps
    ``(file_path, start_line)`` to a list of symbol node IDs.
    """
    file_lookup = file_node_lookup or {}
    sym_lookup = symbol_lookup or {}
    diagnostics: list[dict[str, Any]] = []

    alert_id = str(alert.get("alert_id") or alert.get("fingerprint") or "")
    if not alert_id:
        raise ValueError("alert_id is required")
    rule_id = str(alert.get("rule_id") or "unknown")
    rule_family = str(alert.get("rule_family") or "other")
    cwe_ids = list(alert.get("cwe_ids") or [])
    file_path = alert.get("file_path")
    locations = alert.get("locations")
    span_obj: AlertSpan | None = None
    if not file_path:
        if not locations:
            diagnostics.append({"code": "no_location", "alert_id": alert_id})
        else:
            diagnostics.append({"code": "no_file_path", "alert_id": alert_id})
        return AlertBinding(
            alert_id=alert_id,
            sarif_alert_ref=str(alert.get("sarif_alert_ref") or alert_id),
            rule_id=rule_id,
            rule_family=rule_family,
            cwe_ids=cwe_ids,
            graph_snapshot_id=graph_snapshot_id,
            confidence=BindingConfidence.NONE,
            diagnostics=diagnostics,
        )

    span_obj = AlertSpan(
        file_path=str(file_path),
        start_line=alert.get("start_line"),
        start_column=alert.get("start_column"),
        end_line=alert.get("end_line"),
        end_column=alert.get("end_column"),
    )
    file_node_id = file_lookup.get(str(file_path))
    primary_symbol_ids: list[str] = []
    if alert.get("start_line") is not None:
        primary_symbol_ids = list(
            sym_lookup.get((str(file_path), int(alert["start_line"])), [])
        )

    flow_nodes: list[str] = []
    cross_file_nodes: list[str] = []
    for flow in alert.get("dataflow") or []:
        flow_file = flow.get("file_path")
        flow_line = flow.get("start_line")
        if flow_file and flow_line is not None:
            ids = sym_lookup.get((str(flow_file), int(flow_line)), [])
            flow_nodes.extend(ids)
            if flow_file != file_path:
                cross_file_nodes.extend(ids)

    if (
        sarif_snapshot_id
        and graph_snapshot_id
        and sarif_snapshot_id != graph_snapshot_id
    ):
        diagnostics.append(
            {
                "code": "stale_snapshot",
                "graph_snapshot_id": graph_snapshot_id,
                "sarif_snapshot_id": sarif_snapshot_id,
            }
        )

    if file_node_id and primary_symbol_ids:
        confidence = BindingConfidence.PARSER
    elif file_node_id:
        confidence = BindingConfidence.ANALYSER
    else:
        confidence = BindingConfidence.HEURISTIC

    return AlertBinding(
        alert_id=alert_id,
        sarif_alert_ref=str(alert.get("sarif_alert_ref") or alert_id),
        rule_id=rule_id,
        rule_family=rule_family,
        cwe_ids=cwe_ids,
        file_node_id=file_node_id,
        file_path=str(file_path),
        span=span_obj,
        primary_symbol_node_ids=primary_symbol_ids,
        related_symbol_node_ids=[],
        dataflow_path_nodes=flow_nodes,
        cross_file_nodes=cross_file_nodes,
        graph_snapshot_id=graph_snapshot_id,
        confidence=confidence,
        diagnostics=diagnostics,
    )


__all__ = ["bind_alert"]
