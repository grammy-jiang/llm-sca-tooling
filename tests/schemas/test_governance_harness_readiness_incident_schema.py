from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.schemas.enums import DriftClassification, HarnessStage, PermissionMode, PolicyAction, RedactionStatus, Severity, SideEffectClass
from llm_sca_tooling.schemas.governance import ContextBudget, ManifestHash, RedactionPolicy, RetryPolicy, RuntimeRef, SandboxDescriptor, ToolPermission, VerificationGate, baseline_hard_constraints
from llm_sca_tooling.schemas.harness import HarnessCondition, SamplingCapability
from llm_sca_tooling.schemas.incidents import Incident, IncidentStatus, PromotionCandidate, PromotionReviewState, PromotionTargetType
from llm_sca_tooling.schemas.memory import RetentionPolicy, TrajectoryRef
from llm_sca_tooling.schemas.readiness import AIReadinessReport, AxisScore, DriftFinding, NoRegressionResult, ReadinessAxis, ReadinessAxisHistory, ThresholdResult
from llm_sca_tooling.schemas.supply_chain import ComponentType, SupplyChainRecord

TS = "2026-05-09T00:00:00Z"


def permission() -> ToolPermission:
    return ToolPermission(
        tool_name="apply_patch",
        required_mode=PermissionMode.EDIT,
        path_scope="repo",
        network_requirement="none",
        side_effect_class=SideEffectClass.WRITES_REPO,
        approval_requirement="not_required",
    )


def test_governance_baseline_constraints_are_representable() -> None:
    constraints = baseline_hard_constraints()
    assert [constraint.constraint_id for constraint in constraints] == ["HC1", "HC2", "HC3", "HC4", "HC5", "HC6"]


def test_harness_condition_requires_core_sections(provenance) -> None:
    condition = HarnessCondition(
        harness_condition_id="harness:demo",
        captured_ts=TS,
        runtime=RuntimeRef(runtime_id="runtime:copilot", name="copilot-cli", version="1.0"),
        manifest_hashes=[ManifestHash(path="AGENTS.md", sha256="hash")],
        toolset_hash="hash:tools",
        exposed_tools=[permission()],
        permission_profile="default",
        sandbox=SandboxDescriptor(kind="devcontainer", writes_allowed=True, network_allowed=False, path_scope="repo"),
        network_policy="deny-by-default",
        context_policy=ContextBudget(max_tokens=1000),
        retry_policy=RetryPolicy(max_retries=1),
        verification_gates=[VerificationGate(gate_name="tests", gate_type="unit_test", required=True)],
        telemetry_location=".agent/logs",
        redaction_policy=RedactionPolicy(policy_id="redaction:default", default_status=RedactionStatus.REDACTED),
        sampling_capability=SamplingCapability.UNKNOWN,
        provenance=provenance,
    )
    assert condition.permission_profile == "default"


def test_relaxed_drift_blocks_release(provenance) -> None:
    with pytest.raises(ValidationError):
        DriftFinding(
            drift_id="drift:1",
            target_ref="AGENTS.md",
            classification=DriftClassification.RELAXED,
            severity=Severity.ERROR,
            description="relaxed hard constraint",
            blocks_release=False,
            recommended_action="remove relaxation",
            provenance=provenance,
        )


def test_readiness_scores_and_regressions(repo, provenance) -> None:
    report = AIReadinessReport(
        readiness_report_id="ready:1",
        repo=repo,
        stage=HarnessStage.S1,
        total_score=5,
        axis_scores=[AxisScore(axis=axis, score=1) for axis in ReadinessAxis],
        threshold_result=ThresholdResult(target_stage=HarnessStage.S1, passed=True, reason="baseline met"),
        no_regression_result=NoRegressionResult(passed=True, reason="first report"),
        provenance=provenance,
    )
    assert report.total_score == 5
    with pytest.raises(ValidationError):
        ReadinessAxisHistory(
            history_id="hist:1",
            repo=repo,
            axis=ReadinessAxis.SECURITY,
            previous_score=3,
            current_score=2,
            delta=-1,
            source_report_id=report.readiness_report_id,
            provenance=provenance,
        )


def test_incident_and_promotion_source_links_are_required(provenance) -> None:
    with pytest.raises(ValidationError):
        Incident(
            incident_id="incident:1",
            severity=Severity.HIGH,
            status=IncidentStatus.OPEN,
            title="Loop",
            impact="lost time",
            provenance=provenance,
        )
    with pytest.raises(ValidationError):
        PromotionCandidate(
            promotion_id="promotion:1",
            source_run_id="run:1",
            source_event_ids=[],
            target_type=PromotionTargetType.MEMORY,
            target_ref="memory:1",
            lesson_summary="avoid loop",
            review_state=PromotionReviewState.REVIEWED,
            owner="team",
            review_due_ts=TS,
            rollback_path="delete memory:1",
            provenance=provenance,
        )


def test_memory_and_supply_chain_records_are_representable(repo, provenance) -> None:
    retention = RetentionPolicy(
        retention_class="bounded",
        review_due_ts=TS,
        owner="team",
        exportable=False,
        delete_supported=True,
        redaction_status=RedactionStatus.REDACTED,
        rollback_path="delete trajectory",
    )
    trajectory = TrajectoryRef(trajectory_id="traj:1", repo=repo, source_run_id="run:1", utility=0.5, retention=retention, provenance=provenance)
    supply = SupplyChainRecord(
        supply_chain_record_id="supply:1",
        component_type=ComponentType.ANALYSER,
        name="semgrep",
        version="1.0",
        source="lockfile",
        captured_ts=TS,
        provenance=provenance,
    )
    assert trajectory.retention.owner == "team"
    assert supply.component_type == ComponentType.ANALYSER
