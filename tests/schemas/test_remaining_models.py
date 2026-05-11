"""Smoke-level tests for remaining schema modules (sarif, supply_chain, memory, validation)."""

from __future__ import annotations

from llm_sca_tooling.schemas.memory import (
    RetentionClass,
    RetentionPolicy,
    TrajectoryRef,
)
from llm_sca_tooling.schemas.provenance import (
    ArtifactKind,
    ArtifactRef,
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    PolicyAction,
    RedactionStatus,
    SnapshotRef,
)
from llm_sca_tooling.schemas.sarif import SarifAlertRef, SarifRunRef, SarifSeverity
from llm_sca_tooling.schemas.supply_chain import ComponentType, SupplyChainRecord
from llm_sca_tooling.schemas.validation import (
    validate_evidence_bundle,
    validate_graph_document,
    validate_provenance_completeness,
    validate_run_sequence,
    validate_snapshot_consistency,
    validate_verdict,
)

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


# ---------------------------------------------------------------------------
# SARIF reference models
# ---------------------------------------------------------------------------


def test_sarif_run_ref(parser_provenance, repo_ref, snapshot_ref) -> None:
    ref = SarifRunRef(
        sarif_run_id="sarif:1",
        repo=repo_ref,
        snapshot=snapshot_ref,
        analyzer_name="bandit",
        analyzer_version="1.7",
        provenance=parser_provenance,
    )
    assert ref.analyzer_name == "bandit"


def test_sarif_alert_ref(parser_provenance) -> None:
    alert = SarifAlertRef(
        alert_id="alert:1",
        sarif_run_id="sarif:1",
        rule_id="B101",
        severity=SarifSeverity.warning,
        confidence=0.9,
        provenance=parser_provenance,
    )
    assert alert.severity == SarifSeverity.warning


# ---------------------------------------------------------------------------
# Contract and patch models
# ---------------------------------------------------------------------------


def test_contract_artifact_preserves_status_and_diagnostics(
    parser_provenance, source_span
) -> None:
    from llm_sca_tooling.schemas.contracts import (
        ArtifactRunStatus,
        ArtifactType,
        ContractArtifact,
    )
    from llm_sca_tooling.schemas.graph import (
        GraphDiagnostic,
        GraphDiagnosticSeverity,
    )

    artifact = ContractArtifact(
        artifact_id="contract:1",
        clause_id="clause:auth",
        language="python",
        artifact_type=ArtifactType.pytest,
        target_symbols=["auth.login"],
        source_clause_span=source_span,
        compile_status=ArtifactRunStatus.passed,
        last_run_status=ArtifactRunStatus.failed,
        confidence=0.4,
        provenance=parser_provenance,
        artifact_ref=ArtifactRef(
            artifact_id="art:contract",
            kind=ArtifactKind.test_output,
            uri="artifact://contract",
            redaction_status=RedactionStatus.not_required,
        ),
        diagnostics=[
            GraphDiagnostic(
                diagnostic_id="diag:1",
                severity=GraphDiagnosticSeverity.warning,
                code="contract_failed",
                message="contract did not pass",
                provenance=parser_provenance,
            )
        ],
    )
    assert artifact.artifact_type == ArtifactType.pytest
    assert artifact.diagnostics[0].code == "contract_failed"


def test_patch_record_and_risk_finding_round_trip(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.patches import PatchRecord, RiskClass, RiskFinding

    target_snapshot = SnapshotRef(
        repo_id=REPO_ID,
        git_sha="fedcba9876543210fedcba9876543210fedcba98",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    patch = PatchRecord(
        patch_id="patch:1",
        diff_id="diff:1",
        repo=repo_ref,
        base_snapshot=snapshot_ref,
        target_snapshot=target_snapshot,
        changed_files=["src/app.py"],
        changed_symbols=["app.handler"],
        diff_artifact=ArtifactRef(
            artifact_id="art:diff",
            kind=ArtifactKind.diff,
            uri="artifact://diff",
            redaction_status=RedactionStatus.redacted,
        ),
        generated_by_run_id="run:1",
        provenance=parser_provenance,
        attributes={"phase": "test"},
    )
    finding = RiskFinding(
        finding_id="risk:1",
        diff_id=patch.diff_id,
        changed_symbols=patch.changed_symbols,
        risk_class=RiskClass.risky,
        calibrated_probability=0.7,
        ece_bucket="0.6-0.8",
        policy_action=PolicyAction.approval_required,
        evidence_bundle_id="bundle:1",
        provenance=parser_provenance,
        uncertainty="needs reviewer confirmation",
    )

    assert patch.model_validate(patch.model_dump()).patch_id == "patch:1"
    assert finding.risk_class == RiskClass.risky


# ---------------------------------------------------------------------------
# Supply-chain model
# ---------------------------------------------------------------------------


def test_supply_chain_record(parser_provenance) -> None:
    rec = SupplyChainRecord(
        supply_chain_record_id="sc:1",
        component_type=ComponentType.analyser,
        name="bandit",
        version="1.7.0",
        source="pypi",
        captured_ts=NOW,
        provenance=parser_provenance,
    )
    assert rec.component_type == ComponentType.analyser


# ---------------------------------------------------------------------------
# Memory reference models
# ---------------------------------------------------------------------------


def test_retention_policy_default() -> None:
    policy = RetentionPolicy()
    assert policy.retention_class == RetentionClass.session


def test_trajectory_ref(parser_provenance, repo_ref) -> None:
    traj = TrajectoryRef(
        trajectory_id="traj:1",
        repo=repo_ref,
        source_run_id="run:1",
        provenance=parser_provenance,
    )
    assert traj.trajectory_id == "traj:1"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def test_validate_provenance_completeness_valid(parser_provenance) -> None:
    errors = validate_provenance_completeness(parser_provenance)
    assert errors == []


def test_validate_provenance_completeness_mismatched_repo(
    repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.provenance import Provenance

    other_snapshot = SnapshotRef(
        repo_id="repo:other",
        git_sha=snapshot_ref.git_sha,
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    prov = Provenance.model_construct(
        source_tool="tree-sitter",
        repo=repo_ref,
        snapshot=other_snapshot,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
    errors = validate_provenance_completeness(prov)
    assert any("repo_id" in error for error in errors)


def test_validate_provenance_completeness_constructed_invalid(
    repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.provenance import Provenance

    prov = Provenance.model_construct(
        source_tool="",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.parser,
        confidence=2.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
    errors = validate_provenance_completeness(prov)
    assert "provenance.source_tool is missing" in errors
    assert any("outside [0, 1]" in error for error in errors)


def test_validate_graph_document_no_edges(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.graph import GraphDocument

    doc = GraphDocument(
        graph_id="g1",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
    )
    errors = validate_graph_document(doc)
    assert errors == []


def test_validate_graph_document_reports_missing_and_invalid_edges(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.graph import (
        GraphDocument,
        GraphEdge,
        GraphEdgeType,
        GraphNode,
        GraphNodeType,
    )

    doc = GraphDocument(
        graph_id="g-invalid",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
        nodes=[
            GraphNode(
                node_id="node:file",
                node_type=GraphNodeType.file,
                label="app.py",
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=parser_provenance,
                created_ts=NOW,
            ),
            GraphNode(
                node_id="node:function",
                node_type=GraphNodeType.function,
                label="handler",
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=parser_provenance,
                created_ts=NOW,
            ),
        ],
        edges=[
            GraphEdge(
                edge_id="edge:missing-target",
                edge_type=GraphEdgeType.imports,
                source_id="node:file",
                target_id="node:missing",
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=parser_provenance,
                created_ts=NOW,
            ),
            GraphEdge(
                edge_id="edge:invalid-pair",
                edge_type=GraphEdgeType.calls,
                source_id="node:file",
                target_id="node:function",
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=parser_provenance,
                created_ts=NOW,
            ),
        ],
    )
    errors = validate_graph_document(doc)
    assert any("target_id" in error for error in errors)
    assert any("calls" in error for error in errors)


def test_validate_graph_document_reports_missing_source_and_mixed(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.graph import GraphDocument, GraphEdge, GraphEdgeType

    other_snapshot = SnapshotRef(
        repo_id=REPO_ID,
        git_sha="2222222222222222222222222222222222222222",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    doc = GraphDocument(
        graph_id="g-mixed-source",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
        edges=[
            GraphEdge(
                edge_id="edge:missing-source",
                edge_type=GraphEdgeType.imports,
                source_id="node:missing",
                target_id="node:also-missing",
                repo=repo_ref,
                snapshot=other_snapshot,
                provenance=parser_provenance,
                created_ts=NOW,
            )
        ],
    )
    errors = validate_graph_document(doc)
    assert any("source_id" in error for error in errors)
    assert any("mixed snapshots" in error for error in errors)


def test_validate_run_sequence_valid(parser_provenance) -> None:
    from llm_sca_tooling.schemas.run_records import (
        ActorType,
        RunEvent,
        RunEventType,
        RunRecord,
    )

    record = RunRecord(run_id="run:1", start_ts=NOW, created_ts=NOW)
    events = [
        RunEvent(
            event_id="e1",
            run_id="run:1",
            seq=1,
            ts=NOW,
            type=RunEventType.session_start,
            actor=ActorType.system,
            stage="start",
            redaction_status=RedactionStatus.not_required,
        )
    ]
    errors = validate_run_sequence(record, events)
    assert errors == []


def test_validate_run_sequence_completed_without_harness() -> None:
    from llm_sca_tooling.schemas.run_records import RunRecord, RunStatus

    record = RunRecord(
        run_id="run:complete",
        start_ts=NOW,
        end_ts=NOW,
        status=RunStatus.completed,
        created_ts=NOW,
    )
    errors = validate_run_sequence(record, [])
    assert any("harness_condition_id" in error for error in errors)


def test_validate_run_sequence_constructed_missing_redaction_and_end() -> None:
    from llm_sca_tooling.schemas.run_records import (
        ActorType,
        RunEvent,
        RunEventType,
        RunRecord,
        RunStatus,
    )

    record = RunRecord.model_construct(
        run_id="run:constructed",
        start_ts=NOW,
        end_ts=None,
        status=RunStatus.completed,
        created_ts=NOW,
        harness_condition_id="hc:1",
    )
    event = RunEvent.model_construct(
        event_id="event:constructed",
        run_id="run:constructed",
        seq=1,
        ts=NOW,
        type=RunEventType.session_start,
        actor=ActorType.system,
        stage="start",
        redaction_status=None,
    )
    errors = validate_run_sequence(record, [event])
    assert any("redaction_status" in error for error in errors)
    assert any("missing end_ts" in error for error in errors)


def test_validate_evidence_bundle_no_evidence(parser_provenance) -> None:
    from llm_sca_tooling.schemas.evidence import EvidenceBundle

    bundle = EvidenceBundle(
        bundle_id="b1",
        subject_ref="s1",
        created_ts=NOW,
        provenance=parser_provenance,
    )
    errors = validate_evidence_bundle(bundle)
    assert errors == []


def test_validate_evidence_bundle_soft_llm_warning(llm_provenance) -> None:
    from llm_sca_tooling.schemas.evidence import (
        EvidenceBundle,
        EvidenceItem,
        EvidenceSupport,
    )

    bundle = EvidenceBundle(
        bundle_id="b-soft",
        subject_ref="s1",
        evidence_items=[
            EvidenceItem(
                evidence_id="e-soft",
                kind="llm_claim",
                supports=EvidenceSupport.supports,
                strength=EvidenceStrength.soft_llm,
                confidence=0.5,
                provenance=llm_provenance,
            )
        ],
        created_ts=NOW,
        provenance=llm_provenance,
    )
    errors = validate_evidence_bundle(bundle)
    assert any("soft_llm" in error for error in errors)


def test_validate_verdict_unknown_no_uncertainty(parser_provenance) -> None:
    from llm_sca_tooling.schemas.provenance import PolicyAction
    from llm_sca_tooling.schemas.verdicts import Verdict, VerdictValue

    v = Verdict(
        verdict_id="v:1",
        workflow="test",
        subject_ref="s1",
        verdict=VerdictValue.unknown,
        confidence=0.0,
        evidence_bundle_id="b:1",
        recommended_action="investigate",
        policy_action=PolicyAction.not_applicable,
        provenance=parser_provenance,
    )
    errors = validate_verdict(v)
    assert any("uncertainty" in e for e in errors)


def test_validate_verdict_positive_without_reasoning_is_allowed(
    parser_provenance,
) -> None:
    from llm_sca_tooling.schemas.verdicts import Verdict, VerdictValue

    v = Verdict(
        verdict_id="v:safe",
        workflow="test",
        subject_ref="s1",
        verdict=VerdictValue.safe,
        confidence=0.9,
        evidence_bundle_id="b:1",
        recommended_action="merge",
        policy_action=PolicyAction.allow,
        provenance=parser_provenance,
    )
    assert validate_verdict(v) == []


def test_validate_verdict_constructed_positive_soft_only(
    parser_provenance,
) -> None:
    from llm_sca_tooling.schemas.verdicts import (
        ReasoningStep,
        Verdict,
        VerdictValue,
    )

    v = Verdict.model_construct(
        verdict_id="v:constructed",
        workflow="test",
        subject_ref="s1",
        verdict=VerdictValue.safe,
        confidence=0.9,
        evidence_bundle_id="b:1",
        reasoning_chain=[
            ReasoningStep(
                step_id="step:1",
                claim="looks safe",
                strength=EvidenceStrength.soft_llm,
            )
        ],
        uncertainty=[],
        recommended_action="merge",
        policy_action=PolicyAction.allow,
        provenance=parser_provenance,
    )
    errors = validate_verdict(v)
    assert any("only by soft_llm" in error for error in errors)


def test_validate_snapshot_consistency_clean(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.graph import GraphDocument

    doc = GraphDocument(
        graph_id="g1",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
    )
    errors = validate_snapshot_consistency(doc)
    assert errors == []


def test_validate_snapshot_consistency_dirty_and_mixed(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    from llm_sca_tooling.schemas.graph import GraphDocument, GraphNode, GraphNodeType

    dirty_snapshot = SnapshotRef(
        repo_id=REPO_ID,
        git_sha=snapshot_ref.git_sha,
        worktree_snapshot_id="wt:dirty",
        branch="main",
        dirty=True,
        index_status=IndexStatus.partial,
        captured_ts=NOW,
    )
    doc = GraphDocument(
        graph_id="g-dirty",
        repo=repo_ref,
        snapshot=dirty_snapshot,
        generated_by="test",
        generated_ts=NOW,
        nodes=[
            GraphNode(
                node_id="node:dirty",
                node_type=GraphNodeType.file,
                label="app.py",
                repo=repo_ref,
                snapshot=SnapshotRef(
                    repo_id=REPO_ID,
                    git_sha="1111111111111111111111111111111111111111",
                    branch="main",
                    dirty=False,
                    index_status=IndexStatus.fresh,
                    captured_ts=NOW,
                ),
                provenance=parser_provenance,
                created_ts=NOW,
            )
        ],
    )
    errors = validate_snapshot_consistency(doc)
    assert any("dirty" in error for error in errors)
    assert any("different snapshots" in error for error in errors)
