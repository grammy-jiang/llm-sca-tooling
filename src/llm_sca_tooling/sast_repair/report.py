"""SAST repair orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.patch_review.risk_classifier import classify_patch_risk
from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.analyser_rerun import rerun_analyser
from llm_sca_tooling.sast_repair.build_test_runner import run_build_and_tests
from llm_sca_tooling.sast_repair.models import SASTRepairReport
from llm_sca_tooling.sast_repair.patch_generator import NullPatchGenerator
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.remaining_risk import make_remaining_risk_note
from llm_sca_tooling.sast_repair.repair_context import build_repair_context
from llm_sca_tooling.sast_repair.sandbox import apply_patch_in_sandbox
from llm_sca_tooling.sast_repair.sarif_delta_verifier import verify_sarif_delta
from llm_sca_tooling.sast_repair.suppression import propose_suppression


def run_sast_repair(
    *,
    alert: dict[str, Any],
    run_id: str = "sast-repair:null",
    graph_snapshot_id: str | None = "snapshot:null",
    before_alerts: list[dict[str, Any]] | None = None,
    after_alerts: list[dict[str, Any]] | None = None,
    generate_patch: bool = True,
    sandbox_root: Path | None = None,
    suppression_history: list[str] | None = None,
    newly_failing_tests: list[str] | None = None,
) -> SASTRepairReport:
    binding = bind_alert(alert, graph_snapshot_id=graph_snapshot_id)
    classification = classify_alert(binding, suppression_history=suppression_history)
    metadata = extract_predicate_metadata(binding)
    examples, _diagnostics = get_predicate_examples(metadata=metadata)
    context = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=examples,
    )
    suppression = propose_suppression(
        classification=classification, rule_id=binding.rule_id
    )
    patch = (
        None
        if suppression and not generate_patch
        else NullPatchGenerator().generate(context)
    )
    sandbox = apply_patch_in_sandbox(
        patch=patch or NullPatchGenerator().generate(context),
        workspace_root=sandbox_root,
    )
    rerun = rerun_analyser(alert_id=binding.alert_id, sandbox=sandbox)
    before = before_alerts if before_alerts is not None else [alert]
    after = after_alerts if after_alerts is not None else []
    sarif = verify_sarif_delta(
        alert_id=binding.alert_id,
        before_alerts=before,
        after_alerts=after,
        after_run_id=rerun.sarif_run_id_after,
    )
    build_tests = run_build_and_tests(
        alert_id=binding.alert_id,
        sandbox=sandbox,
        newly_failing_tests=newly_failing_tests,
    )
    risk, _vector, _ctx = classify_patch_risk(
        diff_text=patch.diff_text if patch else "",
        after_failed=build_tests.newly_failing_tests,
    )
    remaining = make_remaining_risk_note(
        alert_id=binding.alert_id,
        sarif=sarif,
        build_tests=build_tests,
        vulnerability_class=bool(
            binding.cwe_ids or binding.rule_family in {"injection", "nullderef"}
        ),
    )
    hcs = HarnessConditionSheet.create(run_id=run_id)
    verdict = _verdict(
        sarif, build_tests, suppression is not None, remaining.risk_level
    )
    return SASTRepairReport(
        report_id=f"sast-repair:{binding.alert_id}",
        alert_id=binding.alert_id,
        run_id=run_id,
        harness_condition_id=hcs.hcs_id,
        alert_binding_ref=f"binding:{binding.alert_id}",
        alert_classification_ref=f"classification:{binding.alert_id}",
        predicate_examples_ref=f"predicate://examples/{binding.rule_id}",
        repair_context_ref=f"repair-context:{binding.alert_id}",
        patch_ref=f"patch:{binding.alert_id}" if patch else None,
        suppression_proposal_ref=(
            f"suppression:{binding.alert_id}" if suppression else None
        ),
        sarif_delta_ref=f"sarif-delta:{binding.alert_id}",
        build_test_result_ref=f"build-test:{binding.alert_id}",
        patch_risk_result_ref=f"patch-risk:{risk.diff_id}",
        remaining_risk_note_ref=f"remaining-risk:{binding.alert_id}",
        success=verdict
        in {"alert_fixed", "alert_fixed_with_risk", "false_positive_suppressed"},
        verdict=verdict,
        recommendation=(
            "review-required" if remaining.risk_level != "none" else "merge-supporting"
        ),
    )


def _verdict(sarif: Any, build_tests: Any, suppressed: bool, risk_level: str) -> str:
    if suppressed:
        return "false_positive_suppressed"
    if sarif.new_critical_or_error_alerts:
        return "repair_blocked"
    if sarif.original_alert_remains:
        return "repair_failed"
    if build_tests.newly_failing_tests:
        return "repair_failed"
    if sarif.success and risk_level != "none":
        return "alert_fixed_with_risk"
    if sarif.success:
        return "alert_fixed"
    return "unknown"
