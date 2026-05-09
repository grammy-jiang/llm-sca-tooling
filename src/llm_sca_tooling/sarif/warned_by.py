"""Create SARIF evidence graph nodes and warned_by edges."""

from __future__ import annotations

from llm_sca_tooling.sarif.models import (
    NormalizedAlert,
    NormalizedRule,
    NormalizedSarifRun,
)
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
)
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SourceSpan, make_provenance
from llm_sca_tooling.storage.ids import stable_hash
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class WarnedByEmitter:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def emit_run(
        self, run: NormalizedSarifRun
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        snapshot = self.workspace.snapshots.get_snapshot(run.snapshot_id).snapshot
        repo_row = self.workspace.repositories.get_repo(run.repo_id)
        repo = RepoRef(
            repo_id=repo_row.repo_id,
            name=repo_row.name,
            root_ref=repo_row.root_path_hash,
            remote_url_hash=repo_row.remote_url_hash,
            default_branch=repo_row.default_branch,
        )
        rule_nodes = [self._rule_node(repo, snapshot, run, rule) for rule in run.rules]
        alert_nodes = [
            self._alert_node(repo, snapshot, run, alert) for alert in run.alerts
        ]
        nodes = [*rule_nodes, *alert_nodes]
        for node in nodes:
            self.workspace.graph.upsert_node(node)
        edges: list[GraphEdge] = []
        for alert in run.alerts:
            targets = []
            if alert.bound_symbol_node_ids:
                targets.extend(
                    (node_id, "primary" if index == 0 else "secondary")
                    for index, node_id in enumerate(alert.bound_symbol_node_ids)
                )
            elif alert.bound_file_node_id:
                targets.append((alert.bound_file_node_id, "file_only"))
            source_id = alert_node_id(alert.alert_id)
            for target_id, binding_type in targets:
                if target_id == source_id:
                    continue
                edge = self._edge(
                    repo, snapshot, run, alert, source_id, target_id, binding_type
                )
                self.workspace.graph.upsert_edge(edge)
                edges.append(edge)
        return nodes, edges

    def _rule_node(
        self, repo: RepoRef, snapshot, run: NormalizedSarifRun, rule: NormalizedRule
    ) -> GraphNode:
        provenance = make_provenance(
            source_tool=run.analyser_id,
            repo=repo,
            snapshot=snapshot,
            derivation=DerivationType.ANALYSER,
            evidence_strength=EvidenceStrength.HARD_STATIC,
            confidence=0.9,
            source_run_id=run.run_id,
            attributes={"rule_id": rule.rule_id},
        )
        return GraphNode(
            node_id=rule_node_id(run.run_id, rule.rule_id),
            node_type=GraphNodeType.SAST_RULE,
            label=rule.rule_id,
            qualified_name=f"{rule.analyser_id}:{rule.rule_id}",
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            properties=rule.model_dump(mode="json"),
            created_ts=_now_ts(),
        )

    def _alert_node(
        self, repo: RepoRef, snapshot, run: NormalizedSarifRun, alert: NormalizedAlert
    ) -> GraphNode:
        span = None
        if alert.file_path and alert.start_line:
            span = SourceSpan(
                file_path=alert.file_path,
                start_line=alert.start_line,
                start_col=alert.start_column,
                end_line=alert.end_line or alert.start_line,
                end_col=alert.end_column,
            )
        strength = (
            EvidenceStrength.STRUCTURED_REPOSITORY
            if alert.suppressed or not alert.bound_symbol_node_ids
            else EvidenceStrength.HARD_STATIC
        )
        provenance = make_provenance(
            source_tool=run.analyser_id,
            repo=repo,
            snapshot=snapshot,
            derivation=DerivationType.ANALYSER,
            evidence_strength=strength,
            confidence=0.8 if alert.binding_confidence != "none" else 0.0,
            source_run_id=run.run_id,
            file=alert.file_path,
            span=span,
            attributes={"alert_id": alert.alert_id, "rule_id": alert.rule_id},
        )
        return GraphNode(
            node_id=alert_node_id(alert.alert_id),
            node_type=GraphNodeType.SARIF_ALERT,
            label=alert.rule_id,
            qualified_name=alert.alert_id,
            repo=repo,
            snapshot=snapshot,
            file_path=alert.file_path,
            span=span,
            provenance=provenance,
            properties=alert.model_dump(mode="json"),
            created_ts=_now_ts(),
        )

    def _edge(
        self,
        repo: RepoRef,
        snapshot,
        run: NormalizedSarifRun,
        alert: NormalizedAlert,
        source_id: str,
        target_id: str,
        binding_type: str,
    ) -> GraphEdge:
        confidence = (
            0.9
            if alert.binding_confidence == "parser"
            else 0.6 if alert.binding_confidence == "heuristic" else 0.0
        )
        provenance = make_provenance(
            source_tool=run.analyser_id,
            repo=repo,
            snapshot=snapshot,
            derivation=DerivationType.ANALYSER,
            evidence_strength=(
                EvidenceStrength.HARD_STATIC
                if confidence >= 0.8
                else EvidenceStrength.STRUCTURED_REPOSITORY
            ),
            confidence=confidence,
            source_run_id=run.run_id,
            file=alert.file_path,
            attributes={"alert_id": alert.alert_id, "rule_id": alert.rule_id},
        )
        return GraphEdge(
            edge_id=f"edge:warned_by:{stable_hash(source_id + '|' + target_id + '|' + binding_type, length=20)}",
            edge_type=GraphEdgeType.WARNED_BY,
            source_id=source_id,
            target_id=target_id,
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            confidence=confidence,
            properties={
                "rule_id": alert.rule_id,
                "analyser_id": alert.analyser_id,
                "run_id": run.run_id,
                "alert_id": alert.alert_id,
                "binding_type": binding_type,
                "suppressed": alert.suppressed,
            },
            created_ts=_now_ts(),
        )


def rule_node_id(run_id: str, rule_id: str) -> str:
    return f"node:sast_rule:{stable_hash(run_id + ':' + rule_id, length=20)}"


def alert_node_id(alert_id: str) -> str:
    return f"node:sarif_alert:{stable_hash(alert_id, length=20)}"
