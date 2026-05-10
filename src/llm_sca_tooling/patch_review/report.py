"""End-to-end patch-review orchestration and tool-callable async entrypoints."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    default_harness_condition_sheet,
)
from llm_sca_tooling.patch_review.ast_diff import extract_ast_diff_features
from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.dryrun import (
    NullDryRUNGenerator,
    degraded_confidence,
    detect_dryrun_mismatches,
)
from llm_sca_tooling.patch_review.four_agent_audit import run_four_agent_audit
from llm_sca_tooling.patch_review.graph_context import extract_graph_context
from llm_sca_tooling.patch_review.interface_compat import check_interface_compatibility
from llm_sca_tooling.patch_review.maintainability_gate import run_maintainability_gate
from llm_sca_tooling.patch_review.merge_policy import derive_recommendation
from llm_sca_tooling.patch_review.models import (
    AuditAxis,
    DiffRecord,
    DryRUNMismatch,
    PatchReviewReport,
    PatchRiskResult,
    Recommendation,
)
from llm_sca_tooling.patch_review.operational_integration import integrate_operational
from llm_sca_tooling.patch_review.risk_classifier import classify
from llm_sca_tooling.patch_review.risk_features import assemble_feature_vector
from llm_sca_tooling.patch_review.sampling_integration import SamplingClient
from llm_sca_tooling.patch_review.sarif_delta import (
    build_sarif_delta,
    empty_sarif_delta,
)
from llm_sca_tooling.patch_review.scope_audit import audit_scope
from llm_sca_tooling.patch_review.symbol_detector import detect_changed_symbols
from llm_sca_tooling.patch_review.test_delta import build_test_delta


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _report_id(diff: DiffRecord) -> str:
    digest = hashlib.sha256(diff.diff_id.encode("utf-8")).hexdigest()
    return f"patch-review:{digest[:24]}"


async def classify_patch_risk(
    *,
    diff: str,
    repo: str | None = None,
    snapshot_before: str | None = None,
    snapshot_after: str | None = None,
    sarif_run_before: str | None = None,
    sarif_run_after: str | None = None,
    run_id: str | None = None,
    sarif_appeared: list[dict[str, Any]] | None = None,
    sarif_disappeared: list[dict[str, Any]] | None = None,
    sarif_severity_changed: list[dict[str, Any]] | None = None,
    sarif_available: bool = True,
    test_results_before: dict[str, str] | None = None,
    test_results_after: dict[str, str] | None = None,
    interface_records: list[dict[str, Any]] | None = None,
    run_events: list[dict[str, Any]] | None = None,
    allowlisted_paths: list[str] | None = None,
    required_tests: list[str] | None = None,
    poc_required: bool = False,
    calibration_family: str | None = None,
    permission_mode: str | None = None,
    budget_hard_stop: bool = False,
    trace_complete: bool | None = None,
) -> dict[str, Any]:
    """Async entrypoint for the ``classify_patch_risk`` tool."""
    parsed = parse_unified_diff(
        diff,
        snapshot_before_id=snapshot_before,
        snapshot_after_id=snapshot_after,
        provenance={"repo": repo} if repo else {},
    )
    symbols = detect_changed_symbols(parsed)
    ast_features = extract_ast_diff_features(parsed)
    graph_context = extract_graph_context(parsed, symbols)
    if sarif_run_before or sarif_run_after or sarif_appeared or sarif_disappeared:
        sarif_delta = build_sarif_delta(
            parsed.diff_id,
            appeared=sarif_appeared,
            disappeared=sarif_disappeared,
            severity_changed=sarif_severity_changed,
            before_run_id=sarif_run_before,
            after_run_id=sarif_run_after,
            available=sarif_available,
        )
    else:
        sarif_delta = empty_sarif_delta(parsed.diff_id)

    test_delta = build_test_delta(
        parsed.diff_id,
        before=test_results_before,
        after=test_results_after,
    )
    interface_compat = check_interface_compatibility(
        parsed, interface_records=interface_records
    )
    scope_audit = audit_scope(
        run_id=run_id,
        changed_paths=parsed.changed_files,
        allowlisted_paths=allowlisted_paths,
        run_events=run_events,
        permission_mode=permission_mode,
        budget_hard_stop=budget_hard_stop,
        trace_complete=trace_complete,
    )
    maintainability = run_maintainability_gate(parsed.diff_text, diff_id=parsed.diff_id)

    feature_vector = assemble_feature_vector(
        diff_id=parsed.diff_id,
        ast_features=ast_features,
        sarif_delta=sarif_delta,
        graph_context=graph_context,
        test_delta=test_delta,
        interface_compat=interface_compat,
        scope_audit=scope_audit,
        maintainability=maintainability,
    )
    risk_result = classify(
        feature_vector,
        sarif_delta=sarif_delta,
        test_delta=test_delta,
        interface_compat=interface_compat,
        scope_audit=scope_audit,
        maintainability=maintainability,
        required_tests=required_tests,
        poc_required=poc_required,
        calibration_family=calibration_family,
    )
    return {
        "diff": parsed.model_dump(mode="json"),
        "feature_vector": feature_vector.model_dump(mode="json"),
        "risk_result": risk_result.model_dump(mode="json"),
        "sarif_delta": sarif_delta.model_dump(mode="json"),
        "scope_audit": scope_audit.model_dump(mode="json"),
        "maintainability": maintainability.model_dump(mode="json"),
        "diagnostics": [
            *parsed.diagnostics,
            *sarif_delta.diagnostics,
            *graph_context.diagnostics,
        ],
    }


async def run_patch_review(
    *,
    diff: str,
    context: dict[str, Any] | None = None,
    repos: list[str] | None = None,
    policy: dict[str, Any] | None = None,
    run_id: str | None = None,
    sampling_client: SamplingClient | None = None,
    sampling_enabled: bool = False,
    task_id: str | None = None,
    sarif_appeared: list[dict[str, Any]] | None = None,
    sarif_disappeared: list[dict[str, Any]] | None = None,
    sarif_severity_changed: list[dict[str, Any]] | None = None,
    sarif_available: bool = True,
    test_results_before: dict[str, str] | None = None,
    test_results_after: dict[str, str] | None = None,
    interface_records: list[dict[str, Any]] | None = None,
    run_events: list[dict[str, Any]] | None = None,
    allowlisted_paths: list[str] | None = None,
    required_tests: list[str] | None = None,
    poc_required: bool = False,
    calibration_family: str | None = None,
    intended_behaviour_change: str | None = None,
    actual_files_changed: list[str] | None = None,
    actual_side_effects: list[str] | None = None,
    invariants_violated: list[str] | None = None,
    risks_materialised: list[str] | None = None,
    incident_ids: list[str] | None = None,
    permission_mode: str | None = None,
    budget_hard_stop: bool = False,
    trace_complete: bool | None = None,
) -> tuple[PatchReviewReport, HarnessConditionSheet]:
    """Async entrypoint for the ``run_patch_review`` tool.

    Returns the typed :class:`PatchReviewReport` plus the
    :class:`HarnessConditionSheet` that governed the run.
    """
    parsed = parse_unified_diff(diff)
    symbols = detect_changed_symbols(parsed)
    ast_features = extract_ast_diff_features(parsed)
    graph_context = extract_graph_context(parsed, symbols)

    if sarif_appeared or sarif_disappeared or sarif_severity_changed:
        sarif_delta = build_sarif_delta(
            parsed.diff_id,
            appeared=sarif_appeared,
            disappeared=sarif_disappeared,
            severity_changed=sarif_severity_changed,
            available=sarif_available,
        )
    else:
        sarif_delta = empty_sarif_delta(parsed.diff_id)
    test_delta = build_test_delta(
        parsed.diff_id, before=test_results_before, after=test_results_after
    )
    interface_compat = check_interface_compatibility(
        parsed, interface_records=interface_records
    )
    scope_audit = audit_scope(
        run_id=run_id,
        changed_paths=parsed.changed_files,
        allowlisted_paths=allowlisted_paths,
        run_events=run_events,
        permission_mode=permission_mode,
        budget_hard_stop=budget_hard_stop,
        trace_complete=trace_complete,
    )
    maintainability = run_maintainability_gate(parsed.diff_text, diff_id=parsed.diff_id)

    feature_vector = assemble_feature_vector(
        diff_id=parsed.diff_id,
        ast_features=ast_features,
        sarif_delta=sarif_delta,
        graph_context=graph_context,
        test_delta=test_delta,
        interface_compat=interface_compat,
        scope_audit=scope_audit,
        maintainability=maintainability,
    )

    prediction = NullDryRUNGenerator().predict(
        parsed, intended_behaviour_change=intended_behaviour_change
    )
    mismatches: list[DryRUNMismatch] = detect_dryrun_mismatches(
        prediction,
        actual_files_changed=actual_files_changed,
        test_delta=test_delta,
        actual_side_effects=actual_side_effects,
        invariants_violated=invariants_violated,
        risks_materialised=risks_materialised,
    )

    risk_result: PatchRiskResult = classify(
        feature_vector,
        sarif_delta=sarif_delta,
        test_delta=test_delta,
        interface_compat=interface_compat,
        scope_audit=scope_audit,
        maintainability=maintainability,
        required_tests=required_tests,
        poc_required=poc_required,
        calibration_family=calibration_family,
    )
    if mismatches:
        risk_result = risk_result.model_copy(
            update={
                "confidence": degraded_confidence(mismatches, risk_result.confidence),
            }
        )

    sampling_used = bool(
        sampling_enabled and sampling_client and sampling_client.available
    )
    audit_findings = run_four_agent_audit(
        parsed,
        sarif_delta=sarif_delta,
        interface_compat=interface_compat,
        sampling_client=sampling_client if sampling_used else None,
    )
    if sampling_used:
        for axis, finding in audit_findings.items():
            audit_findings[axis] = finding.model_copy(update={"sampling_used": True})

    operational = integrate_operational(
        run_id=run_id,
        scope_audit=scope_audit,
        incident_ids=incident_ids,
        budget_hard_stop=budget_hard_stop,
    )
    recommendation: Recommendation = derive_recommendation(
        risk_result,
        operational=operational,
        maintainability=maintainability,
        sarif_delta=sarif_delta,
        scope_audit=scope_audit,
    )

    sheet = default_harness_condition_sheet(
        run_id=run_id or "phase11-null-run",
        model_backend="phase11-null-backend",
        tool_set=("run_patch_review", "classify_patch_risk"),
        permission_mode=permission_mode or "search",
    )

    uncertainty: list[str] = []
    if mismatches:
        uncertainty.append("dryrun_mismatch_detected")
    if not sarif_delta.available:
        uncertainty.append("sarif_unavailable")
    if not graph_context.tests_exercising_changed_nodes:
        uncertainty.append("no_test_coverage_evidence")
    if risk_result.confidence.value != "analyser":
        uncertainty.append(f"risk_confidence:{risk_result.confidence.value}")

    report = PatchReviewReport(
        report_id=_report_id(parsed),
        diff_id=parsed.diff_id,
        run_id=run_id,
        harness_condition_id=sheet.hcs_id,
        correctness_finding=audit_findings[AuditAxis.CORRECTNESS],
        security_finding=audit_findings[AuditAxis.SECURITY],
        performance_finding=audit_findings[AuditAxis.PERFORMANCE],
        compatibility_finding=audit_findings[AuditAxis.COMPATIBILITY],
        sarif_delta_ref=parsed.diff_id if sarif_delta.available else None,
        test_delta_ref=parsed.diff_id,
        interface_compat_result_ref=parsed.diff_id,
        dryrun_prediction_ref=prediction.prediction_id,
        dryrun_mismatches=mismatches,
        scope_audit_result_ref=run_id,
        maintainability_gate_result_ref=maintainability.oracle_result_id,
        patch_risk_result_ref=parsed.diff_id,
        recommendation=recommendation,
        operational_verdict=operational.process_verdict,
        incident_links=incident_ids or [],
        uncertainty=uncertainty,
        sampling_used=sampling_used,
        fallback_mode=not sampling_used,
        created_ts=_now_ts(),
    )
    return report, sheet
