"""Build SARIF graph nodes and warned_by edges."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.sarif.models import (
    NormalizedAlert,
    NormalizedRule,
    NormalizedSarifRun,
)
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    Provenance,
    RepoRef,
    SnapshotRef,
)

__all__ = ["build_sarif_graph_facts"]


def build_sarif_graph_facts(
    run: NormalizedSarifRun, repo_ref: RepoRef, snapshot_ref: SnapshotRef
) -> tuple[list[GraphNode], list[GraphEdge]]:
    rule_nodes = [_rule_node(rule, run, repo_ref, snapshot_ref) for rule in run.rules]
    alert_nodes = [
        _alert_node(alert, run, repo_ref, snapshot_ref) for alert in run.alerts
    ]
    rule_by_id = {
        rule.rule_id: node.node_id
        for rule, node in zip(run.rules, rule_nodes, strict=True)
    }
    edges: list[GraphEdge] = []
    for alert, alert_node in zip(run.alerts, alert_nodes, strict=True):
        for source_id, binding_type in _binding_targets(alert):
            edges.append(
                _warned_by_edge(
                    source_id,
                    alert_node.node_id,
                    alert,
                    run,
                    repo_ref,
                    snapshot_ref,
                    binding_type,
                )
            )
        rule_node_id = rule_by_id.get(alert.rule_id)
        if rule_node_id:
            edges.append(
                _rule_edge(
                    rule_node_id, alert_node.node_id, alert, run, repo_ref, snapshot_ref
                )
            )
    return [*rule_nodes, *alert_nodes], edges


def _rule_node(
    rule: NormalizedRule,
    run: NormalizedSarifRun,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
) -> GraphNode:
    node_id = make_node_id(
        repo_ref.repo_id, "sast_rule", f"{run.run_id}:{rule.rule_id}"
    )
    return GraphNode(
        node_id=node_id,
        node_type=GraphNodeType.sast_rule,
        label=rule.rule_id,
        qualified_name=f"{run.analyser_id}:{rule.rule_id}",
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=_provenance(repo_ref, snapshot_ref, run, confidence=0.8),
        properties=rule.model_dump(mode="json"),
        created_ts=_now(),
    )


def _alert_node(
    alert: NormalizedAlert,
    run: NormalizedSarifRun,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
) -> GraphNode:
    node_id = make_node_id(repo_ref.repo_id, "sarif_alert", alert.alert_id)
    return GraphNode(
        node_id=node_id,
        node_type=GraphNodeType.sarif_alert,
        label=alert.rule_id,
        qualified_name=alert.alert_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        file_path=alert.file_path,
        provenance=_provenance(repo_ref, snapshot_ref, run, confidence=0.7),
        properties=alert.model_dump(mode="json"),
        created_ts=_now(),
    )


def _warned_by_edge(
    source_id: str,
    alert_node_id: str,
    alert: NormalizedAlert,
    run: NormalizedSarifRun,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    binding_type: str,
) -> GraphEdge:
    return GraphEdge(
        edge_id=make_edge_id(repo_ref.repo_id, "warned_by", source_id, alert_node_id),
        edge_type=GraphEdgeType.warned_by,
        source_id=source_id,
        target_id=alert_node_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=_provenance(repo_ref, snapshot_ref, run, confidence=0.7),
        confidence=0.7,
        properties={
            "rule_id": alert.rule_id,
            "alert_id": alert.alert_id,
            "binding_type": binding_type,
            "run_id": run.run_id,
            "analyser_id": run.analyser_id,
            "suppressed": alert.suppressed,
        },
        created_ts=_now(),
    )


def _rule_edge(
    rule_node_id: str,
    alert_node_id: str,
    alert: NormalizedAlert,
    run: NormalizedSarifRun,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
) -> GraphEdge:
    return GraphEdge(
        edge_id=make_edge_id(repo_ref.repo_id, "checks", rule_node_id, alert_node_id),
        edge_type=GraphEdgeType.checks,
        source_id=rule_node_id,
        target_id=alert_node_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=_provenance(repo_ref, snapshot_ref, run, confidence=0.7),
        confidence=0.7,
        properties={"rule_id": alert.rule_id, "run_id": run.run_id},
        created_ts=_now(),
    )


def _binding_targets(alert: NormalizedAlert) -> list[tuple[str, str]]:
    if alert.bound_symbol_node_ids:
        return [
            (node_id, "primary" if index == 0 else "secondary")
            for index, node_id in enumerate(alert.bound_symbol_node_ids)
        ]
    if alert.bound_file_node_id:
        return [(alert.bound_file_node_id, "file_only")]
    return []


def _provenance(
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    run: NormalizedSarifRun,
    *,
    confidence: float,
) -> Provenance:
    return make_provenance(
        repo_ref,
        snapshot_ref,
        source_tool=f"llm-sca-tooling.sarif.{run.analyser_id}",
        source_version=run.analyser_version,
        derivation=DerivationType.analyser,
        evidence_strength=EvidenceStrength.hard_static,
        confidence=confidence,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
