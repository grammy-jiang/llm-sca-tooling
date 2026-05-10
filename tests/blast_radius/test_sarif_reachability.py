"""Tests for SARIF reachability collection."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.sarif_reachability import collect_sarif_reachability
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from tests.blast_radius.conftest import make_edge, make_node


class TestSarifReachability:
    def test_empty_changed_nodes_returns_empty(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        alerts, summary = collect_sarif_reachability([], workspace.graph)
        assert alerts == []
        assert "No SARIF" in summary

    def test_no_sarif_nodes_returns_empty(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_node(changed)
        alerts, summary = collect_sarif_reachability([changed.node_id], workspace.graph)
        assert alerts == []
        assert "No SARIF" in summary

    def test_sarif_alert_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        sarif = make_node(
            "node:alert", GraphNodeType.SARIF_ALERT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, sarif])
        workspace.graph.add_edge(
            make_edge(
                "edge:warned", changed, sarif, provenance, GraphEdgeType.WARNED_BY, 1.0
            )
        )
        alerts, summary = collect_sarif_reachability([changed.node_id], workspace.graph)
        alert_ids = [a["node_id"] for a in alerts]
        assert sarif.node_id in alert_ids
        assert "1 SARIF" in summary

    def test_summary_contains_count(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn3", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        sarif1 = make_node(
            "node:s1", GraphNodeType.SARIF_ALERT, repo_ref, snapshot, provenance
        )
        sarif2 = make_node(
            "node:s2", GraphNodeType.SARIF_ALERT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, sarif1, sarif2])
        workspace.graph.add_edge(
            make_edge("edge:w1", changed, sarif1, provenance, GraphEdgeType.WARNED_BY)
        )
        workspace.graph.add_edge(
            make_edge("edge:w2", changed, sarif2, provenance, GraphEdgeType.WARNED_BY)
        )
        alerts, summary = collect_sarif_reachability([changed.node_id], workspace.graph)
        assert len(alerts) == 2
        assert "2 SARIF" in summary
