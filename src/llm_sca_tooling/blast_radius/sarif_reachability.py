"""Phase 15 SARIF reachability — map static-analysis alerts to changed symbols."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType

if TYPE_CHECKING:
    from llm_sca_tooling.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

_SARIF_NODE_TYPES = {GraphNodeType.SARIF_ALERT, GraphNodeType.SAST_RULE}


def collect_sarif_reachability(
    changed_node_ids: list[str],
    graph_store: GraphStore,
    *,
    max_hops: int = 4,
) -> tuple[list[dict[str, object]], str]:
    """Collect SARIF alert nodes reachable from changed symbols.

    Returns (alert_node_dicts, summary_string).
    """
    alerts: list[dict[str, object]] = []

    try:
        slice_ = graph_store.fetch_ego_graph(
            changed_node_ids,
            depth=max_hops,
            edge_types=[GraphEdgeType.WARNED_BY],
        )
        for node in slice_.nodes:
            if node.node_id in set(changed_node_ids):
                continue
            if node.node_type in _SARIF_NODE_TYPES:
                alerts.append(
                    {
                        "node_id": node.node_id,
                        "node_type": node.node_type.value,
                        "label": node.label,
                        "breaking_change_flag": False,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("SARIF reachability collection failed: %s", exc)

    summary = (
        f"{len(alerts)} SARIF alert(s) reachable from changed symbols."
        if alerts
        else "No SARIF reachability detected."
    )
    return alerts, summary


__all__ = ["collect_sarif_reachability"]
