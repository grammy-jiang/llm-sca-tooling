"""Tests for operational_integration and merge_policy."""

from __future__ import annotations

from llm_sca_tooling.patch_review.merge_policy import derive_recommendation
from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    PatchRiskResult,
    PolicyActionValue,
    ProcessVerdict,
    Recommendation,
    RiskClassValue,
)
from llm_sca_tooling.patch_review.operational_integration import (
    coerce_recommendation,
    integrate_operational,
)
from llm_sca_tooling.patch_review.sarif_delta import (
    build_sarif_delta,
    empty_sarif_delta,
)
from llm_sca_tooling.patch_review.scope_audit import audit_scope


def _events():
    return [
        {"type": "session_start", "event_id": "1"},
        {"type": "harness_condition_recorded", "event_id": "2"},
        {"type": "session_end", "event_id": "3"},
    ]


def _risk(
    action: PolicyActionValue, klass: RiskClassValue = RiskClassValue.SAFE
) -> PatchRiskResult:
    return PatchRiskResult(
        diff_id="d",
        risk_class=klass,
        calibrated_probability=None,
        ece_bucket=None,
        feature_vector_ref="d",
        active_overrides=[],
        classifier_version="deterministic-v1",
        calibration_family=None,
        confidence=ConfidenceLevel.ANALYSER,
        policy_action=action,
    )


def test_integrate_compliant() -> None:
    scope = audit_scope(run_id="r1", changed_paths=[], run_events=_events())
    result = integrate_operational(run_id="r1", scope_audit=scope)
    assert result.process_verdict == ProcessVerdict.PROCESS_COMPLIANT
    assert result.operational_recommendation == Recommendation.MERGE_SUPPORTING


def test_integrate_with_no_scope_run_id_none() -> None:
    result = integrate_operational(run_id=None, scope_audit=None)
    assert result.process_verdict == ProcessVerdict.TRACE_INCOMPLETE
    assert not result.trace_complete


def test_integrate_with_incidents_review_required() -> None:
    scope = audit_scope(run_id="r1", changed_paths=[], run_events=_events())
    result = integrate_operational(
        run_id="r1", scope_audit=scope, incident_ids=["inc-1"]
    )
    assert result.operational_recommendation == Recommendation.REVIEW_REQUIRED
    assert result.incident_count == 1


def test_integrate_noncompliant_blocks() -> None:
    scope = audit_scope(
        run_id="r1",
        changed_paths=["etc"],
        allowlisted_paths=["src/"],
        run_events=_events(),
    )
    result = integrate_operational(run_id="r1", scope_audit=scope)
    assert result.operational_recommendation == Recommendation.BLOCK


def test_integrate_budget_exhausted_review() -> None:
    scope = audit_scope(
        run_id="r1", changed_paths=[], run_events=_events(), budget_hard_stop=True
    )
    result = integrate_operational(
        run_id="r1", scope_audit=scope, budget_hard_stop=True
    )
    assert result.operational_recommendation == Recommendation.REVIEW_REQUIRED


def test_coerce_recommendation_idempotent_and_string() -> None:
    assert coerce_recommendation(Recommendation.BLOCK) == Recommendation.BLOCK
    assert coerce_recommendation("block") == Recommendation.BLOCK


def test_merge_policy_deterministic_block_wins() -> None:
    risk = _risk(PolicyActionValue.BLOCK, RiskClassValue.VULNERABILITY_INTRODUCING)
    rec = derive_recommendation(risk)
    assert rec == Recommendation.BLOCK


def test_merge_policy_sarif_critical_blocks_even_when_safe() -> None:
    risk = _risk(PolicyActionValue.MERGE_SUPPORTING)
    sarif = build_sarif_delta(
        "d", appeared=[{"alert_id": "a", "severity": "critical", "rule_id": "x"}]
    )
    rec = derive_recommendation(risk, sarif_delta=sarif)
    assert rec == Recommendation.BLOCK


def test_merge_policy_scope_violation_blocks() -> None:
    risk = _risk(PolicyActionValue.MERGE_SUPPORTING)
    scope = audit_scope(
        run_id="r1",
        changed_paths=["etc"],
        allowlisted_paths=["src/"],
        run_events=_events(),
    )
    rec = derive_recommendation(risk, scope_audit=scope)
    assert rec == Recommendation.BLOCK


def test_merge_policy_review_required_paths() -> None:
    risk = _risk(PolicyActionValue.REVIEW_REQUIRED, RiskClassValue.UNKNOWN)
    rec = derive_recommendation(risk, sarif_delta=empty_sarif_delta("d"))
    assert rec == Recommendation.REVIEW_REQUIRED


def test_merge_policy_unknown_path() -> None:
    risk = _risk(PolicyActionValue.UNKNOWN, RiskClassValue.UNKNOWN)
    rec = derive_recommendation(risk)
    assert rec == Recommendation.UNKNOWN


def test_merge_policy_clean_merge_supporting() -> None:
    risk = _risk(PolicyActionValue.MERGE_SUPPORTING)
    rec = derive_recommendation(risk, sarif_delta=empty_sarif_delta("d"))
    assert rec == Recommendation.MERGE_SUPPORTING


def test_merge_policy_operational_block_overrides_safe() -> None:
    risk = _risk(PolicyActionValue.MERGE_SUPPORTING)
    scope = audit_scope(
        run_id="r1",
        changed_paths=["etc"],
        allowlisted_paths=["src/"],
        run_events=_events(),
    )
    op = integrate_operational(run_id="r1", scope_audit=scope)
    rec = derive_recommendation(
        risk, operational=op, sarif_delta=empty_sarif_delta("d"), scope_audit=None
    )
    assert rec == Recommendation.BLOCK
