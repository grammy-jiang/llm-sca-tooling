"""Bind SARIF alerts to graph-ish repair context."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import AlertBinding


def bind_alert(
    alert: dict[str, Any], *, graph_snapshot_id: str | None = None
) -> AlertBinding:
    alert_id = str(alert.get("alert_id") or alert.get("fingerprint") or "alert:unknown")
    rule_id = str(alert.get("rule_id") or alert.get("ruleId") or "unknown")
    file_path = alert.get("file_path") or alert.get("path")
    line = int(alert.get("line", 0) or 0)
    diagnostics: list[str] = []
    if file_path is None:
        diagnostics.append("no_location")
    if graph_snapshot_id is None:
        diagnostics.append("stale_or_missing_snapshot")
    confidence = "parser" if file_path and line else "heuristic"
    return AlertBinding(
        alert_id=alert_id,
        sarif_alert_ref=f"sarif://alert/{alert_id}",
        rule_id=rule_id,
        rule_family=_rule_family(rule_id),
        cwe_ids=_cwes(alert),
        file_node_id=f"file:{file_path}" if file_path else None,
        file_path=str(file_path) if file_path else None,
        span=(line, line) if line else None,
        primary_symbol_node_ids=(
            [f"symbol:{file_path}:{line}"] if file_path and line else []
        ),
        graph_snapshot_id=graph_snapshot_id,
        confidence=confidence,
        diagnostics=diagnostics,
    )


def _rule_family(rule_id: str) -> str:
    lower = rule_id.lower()
    if "sql" in lower or "injection" in lower or "cwe-89" in lower:
        return "injection"
    if "null" in lower or "none" in lower:
        return "nullderef"
    return lower.split(".", 1)[0]


def _cwes(alert: dict[str, Any]) -> list[str]:
    raw = alert.get("cwe_ids") or alert.get("cwe") or []
    if isinstance(raw, str):
        return [raw]
    return [str(item) for item in raw] if isinstance(raw, list) else []
