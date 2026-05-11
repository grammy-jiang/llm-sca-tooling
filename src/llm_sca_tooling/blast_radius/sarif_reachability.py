"""SARIF reachability impact (which rules activate if changed code is reached)."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.blast_radius.models import ImpactGroup, ImpactRecord


def compute_sarif_reachability(
    changed_symbol_ids: list[str],
    sarif_alert_nodes: list[dict[str, Any]] | None = None,
) -> list[ImpactRecord]:
    """Return SARIF_REACHABILITY impact records for alerts near changed symbols."""
    alert_nodes = sarif_alert_nodes or []
    records: list[ImpactRecord] = []
    for alert in alert_nodes:
        alert_id = alert.get("node_id") or alert.get("alert_id") or "unknown"
        rule = alert.get("rule_id", "unknown")
        records.append(
            ImpactRecord(
                group=ImpactGroup.sarif_reachability,
                node_id=alert_id,
                node_type="sarif_alert",
                path_from_changed_symbol=changed_symbol_ids[:1],
                hop_distance=1,
                confidence="analyser",
                confirmed=True,
                edge_types_used=["warns_by"],
                change_type_relevance="security",
                breaking_change_flag=alert.get("severity", "warning")
                in {"error", "critical"},
                notes=f"rule:{rule}",
            )
        )
    return records
