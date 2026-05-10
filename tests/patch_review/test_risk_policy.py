"""Tests for risk_features and risk_policy and risk_classifier."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    MaintainabilityGateResult,
    PolicyActionValue,
    ProcessVerdict,
    RiskClassValue,
)
from llm_sca_tooling.patch_review.risk_classifier import (
    MIN_MACRO_F1,
    TrainedClassifier,
    classify,
)
from llm_sca_tooling.patch_review.risk_features import assemble_feature_vector
from llm_sca_tooling.patch_review.risk_policy import apply_deterministic_policy
from llm_sca_tooling.patch_review.sarif_delta import (
    build_sarif_delta,
    empty_sarif_delta,
)
from llm_sca_tooling.patch_review.scope_audit import audit_scope
from llm_sca_tooling.patch_review.test_delta import build_test_delta


def _required_events():
    return [
        {"type": "session_start", "event_id": "1"},
        {"type": "harness_condition_recorded", "event_id": "2"},
        {"type": "session_end", "event_id": "3"},
    ]


def _vector(diff_id: str = "diff:1"):
    return assemble_feature_vector(diff_id=diff_id)


def test_safe_path_with_calibration() -> None:
    fv = _vector()
    sarif = empty_sarif_delta(fv.diff_id)
    result = apply_deterministic_policy(
        fv,
        sarif_delta=sarif,
        test_delta=None,
        interface_compat=None,
        scope_audit=audit_scope(
            run_id="r1", changed_paths=[], run_events=_required_events()
        ),
        maintainability=None,
        calibration_family="python:safe",
    )
    assert result.risk_class == RiskClassValue.SAFE
    assert result.policy_action == PolicyActionValue.MERGE_SUPPORTING


def test_safe_without_calibration_marks_override() -> None:
    fv = _vector()
    sarif = empty_sarif_delta(fv.diff_id)
    result = classify(
        fv,
        sarif_delta=sarif,
        test_delta=None,
        scope_audit=audit_scope(
            run_id="r1", changed_paths=[], run_events=_required_events()
        ),
    )
    assert "calibration_family_missing" in result.active_overrides


def test_critical_sarif_blocks() -> None:
    fv = _vector()
    sarif = build_sarif_delta(
        fv.diff_id,
        appeared=[
            {"alert_id": "a", "rule_id": "py/sql-injection", "severity": "critical"}
        ],
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=sarif,
        test_delta=None,
        interface_compat=None,
        scope_audit=None,
        maintainability=None,
    )
    assert result.risk_class == RiskClassValue.VULNERABILITY_INTRODUCING
    assert result.policy_action == PolicyActionValue.BLOCK


def test_failing_required_test_blocks() -> None:
    fv = _vector()
    td = build_test_delta(
        fv.diff_id,
        before={"t1": "passed"},
        after={"t1": "failed"},
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=td,
        interface_compat=None,
        scope_audit=None,
        maintainability=None,
        required_tests=["t1"],
    )
    assert result.risk_class == RiskClassValue.CORRECT_BUT_OVERFIT
    assert result.policy_action == PolicyActionValue.BLOCK


def test_invalid_repro_with_failing_required_blocks() -> None:
    fv = _vector()
    td = build_test_delta(
        fv.diff_id,
        before={"t1": "passed"},
        after={"t1": "failed"},
        reproduction_test="executed_pass_both",
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=td,
        interface_compat=None,
        scope_audit=None,
        maintainability=None,
        required_tests=["t1"],
    )
    assert "invalid_reproduction_test" in result.active_overrides


def test_poc_failed_blocks() -> None:
    fv = _vector()
    td = build_test_delta(fv.diff_id, poc_plus="failed")
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=td,
        interface_compat=None,
        scope_audit=None,
        maintainability=None,
        poc_required=True,
    )
    assert result.risk_class == RiskClassValue.VULNERABLE
    assert result.policy_action == PolicyActionValue.BLOCK


def test_out_of_scope_blocks() -> None:
    fv = _vector()
    scope = audit_scope(
        run_id="r1",
        changed_paths=["secret"],
        allowlisted_paths=["src/"],
        run_events=_required_events(),
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=None,
        interface_compat=None,
        scope_audit=scope,
        maintainability=None,
    )
    assert result.policy_action == PolicyActionValue.BLOCK
    assert result.confidence == ConfidenceLevel.HEURISTIC


def test_process_problem_yields_unknown() -> None:
    fv = _vector()
    scope = audit_scope(run_id=None, changed_paths=[])
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=None,
        interface_compat=None,
        scope_audit=scope,
        maintainability=None,
    )
    assert result.risk_class == RiskClassValue.UNKNOWN
    assert result.policy_action == PolicyActionValue.UNKNOWN


def test_breaking_iface_review_required() -> None:
    fv = _vector()
    from llm_sca_tooling.patch_review.interface_compat import (
        check_interface_compatibility,
    )

    diff = parse_unified_diff(
        "diff --git a/api/routes/x.py b/api/routes/x.py\n--- a/api/routes/x.py\n+++ b/api/routes/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    iface = check_interface_compatibility(
        diff, interface_records=[{"operation": "/x", "change": "removed"}]
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=None,
        interface_compat=iface,
        scope_audit=audit_scope(
            run_id="r1", changed_paths=[], run_events=_required_events()
        ),
        maintainability=None,
    )
    assert result.policy_action == PolicyActionValue.REVIEW_REQUIRED


def test_dependency_direction_failed_review_required() -> None:
    fv = _vector()
    maint = MaintainabilityGateResult(
        diff_id="d",
        oracle_result_id="o",
        change_locality_pass=True,
        dependency_direction_pass=False,
        responsibility_pass=True,
        reuse_pass=True,
        side_effect_pass=True,
        testability_pass=True,
        overall_pass=False,
        findings=[],
        block_merge=True,
    )
    result = apply_deterministic_policy(
        fv,
        sarif_delta=None,
        test_delta=None,
        interface_compat=None,
        scope_audit=audit_scope(
            run_id="r1", changed_paths=[], run_events=_required_events()
        ),
        maintainability=maint,
    )
    assert result.policy_action == PolicyActionValue.REVIEW_REQUIRED


def test_classifier_calibration_below_threshold() -> None:
    fv = _vector()
    bad = TrainedClassifier(
        version="v1",
        calibration_family="python:safe",
        macro_f1=0.5,
        ece=0.5,
        predict_fn=lambda fv: (_ for _ in ()).throw(
            AssertionError("must not be called")
        ),
    )
    result = classify(
        fv,
        sarif_delta=empty_sarif_delta(fv.diff_id),
        test_delta=None,
        scope_audit=audit_scope(
            run_id="r", changed_paths=[], run_events=_required_events()
        ),
        calibration_family="python:safe",
        trained_classifier=bad,
    )
    assert "classifier_calibration_below_threshold" in result.active_overrides


def test_classifier_calibration_passed_predicts_when_safe() -> None:
    fv = _vector()
    from llm_sca_tooling.patch_review.models import PatchRiskResult

    expected = PatchRiskResult(
        diff_id=fv.diff_id,
        risk_class=RiskClassValue.SAFE,
        calibrated_probability=0.99,
        ece_bucket="0.0-0.1",
        feature_vector_ref=fv.diff_id,
        active_overrides=[],
        classifier_version="v9",
        calibration_family=None,
        confidence=ConfidenceLevel.ANALYSER,
        policy_action=PolicyActionValue.MERGE_SUPPORTING,
    )
    good = TrainedClassifier(
        version="v9",
        calibration_family="python:safe",
        macro_f1=MIN_MACRO_F1,
        ece=0.05,
        predict_fn=lambda fv: expected,
    )
    result = classify(
        fv,
        sarif_delta=empty_sarif_delta(fv.diff_id),
        test_delta=None,
        scope_audit=audit_scope(
            run_id="r", changed_paths=[], run_events=_required_events()
        ),
        calibration_family="python:safe",
        trained_classifier=good,
    )
    assert result.classifier_version == "v9"
    assert result.calibration_family == "python:safe"


def test_feature_vector_includes_refs() -> None:
    from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff

    diff = parse_unified_diff("")
    sarif = empty_sarif_delta(diff.diff_id)
    fv = assemble_feature_vector(
        diff_id=diff.diff_id,
        sarif_delta=sarif,
    )
    assert fv.sarif_delta_ref == diff.diff_id
    assert fv.scope_audit_verdict == ProcessVerdict.UNKNOWN
