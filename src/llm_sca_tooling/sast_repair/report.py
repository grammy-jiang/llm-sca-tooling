"""``run_sast_repair`` workflow orchestrator and SASTRepairReport assembler."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    default_harness_condition_sheet,
)
from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.analyser_rerun import RerunCallable, rerun_analyser
from llm_sca_tooling.sast_repair.build_test_runner import (
    BuildTestRunner,
    run_build_and_tests,
)
from llm_sca_tooling.sast_repair.corpus_adapter import CleanCorpusAdapter
from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertClassification,
    AnalyserRerunResult,
    BindingConfidence,
    BuildTestResult,
    ClassificationConfidence,
    ClassificationValue,
    PredicateMetadata,
    RemainingRiskNote,
    RepairContext,
    RerunStatus,
    SandboxResult,
    SARIFDeltaVerificationResult,
    SASTPatch,
    SASTRepairReport,
    SuppressionProposal,
    Verdict,
)
from llm_sca_tooling.sast_repair.patch_generator import (
    NullPatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.remaining_risk import generate_remaining_risk
from llm_sca_tooling.sast_repair.repair_context import build_repair_context
from llm_sca_tooling.sast_repair.sandbox import SandboxManager
from llm_sca_tooling.sast_repair.sarif_delta_verifier import verify_sarif_delta
from llm_sca_tooling.sast_repair.suppression import propose_suppression

PatchRiskClassifier = Callable[[str, list[str]], Awaitable[dict[str, Any]]]


def _report_id(alert_id: str) -> str:
    digest = hashlib.sha256(alert_id.encode("utf-8")).hexdigest()
    return f"sast-repair-report:{digest[:24]}"


def _decide_verdict(
    *,
    classification: AlertClassification,
    suppression: SuppressionProposal | None,
    sarif_delta: SARIFDeltaVerificationResult | None,
    build_test: BuildTestResult | None,
    remaining_risk: list[RemainingRiskNote],
) -> tuple[Verdict, bool, str]:
    if (
        suppression is not None
        and classification.classification == ClassificationValue.LIKELY_FALSE_POSITIVE
    ):
        return Verdict.FALSE_POSITIVE_SUPPRESSED, True, "review-required"
    if sarif_delta is None:
        return Verdict.UNKNOWN, False, "review-required"
    if sarif_delta.original_alert_remains:
        return Verdict.REPAIR_FAILED, False, "review-required"
    if sarif_delta.new_critical_or_error_alerts:
        return Verdict.REPAIR_BLOCKED, False, "block"
    if build_test is not None and build_test.newly_failing_tests:
        return Verdict.REPAIR_FAILED, False, "review-required"
    if not sarif_delta.original_alert_gone:
        return Verdict.UNKNOWN, False, "review-required"
    if sarif_delta.severity_regressions:
        return Verdict.PARTIALLY_FIXED, False, "review-required"
    has_meaningful_risk = any(
        note.risk_level.value != "none" for note in remaining_risk
    )
    if has_meaningful_risk:
        return Verdict.ALERT_FIXED_WITH_RISK, True, "review-required"
    return Verdict.ALERT_FIXED, True, "merge-supporting"


async def run_sast_repair(
    *,
    alert: dict[str, Any],
    repo_root: Path | None = None,
    corpus_adapter: CleanCorpusAdapter,
    before_alerts: list[dict[str, Any]] | None = None,
    after_alerts: list[dict[str, Any]] | None = None,
    sarif_run_before_id: str | None = None,
    sarif_run_after_id: str | None = None,
    file_node_lookup: dict[str, str] | None = None,
    symbol_lookup: dict[tuple[str, int], list[str]] | None = None,
    graph_snapshot_id: str | None = None,
    sarif_snapshot_id: str | None = None,
    classification_signals: dict[str, Any] | None = None,
    patch_generator: PatchGeneratorInterface | None = None,
    null_mode: bool = True,
    generate_patch: bool = False,
    analyser_id: str = "semgrep",
    analyser_version: str | None = None,
    analyser_runner: RerunCallable | None = None,
    build_test_runner: BuildTestRunner | None = None,
    coverage_map: dict[str, list[str]] | None = None,
    risk_classifier: PatchRiskClassifier | None = None,
    poc_plus_available: bool = False,
    graph_dataflow_complete: bool = False,
    run_id: str | None = None,
    permission_mode: str = "search",
    k: int = 5,
) -> tuple[SASTRepairReport, HarnessConditionSheet]:
    """Execute the full SAST repair loop and return the typed report + HCS."""
    binding = bind_alert(
        alert=alert,
        graph_snapshot_id=graph_snapshot_id,
        sarif_snapshot_id=sarif_snapshot_id,
        file_node_lookup=file_node_lookup,
        symbol_lookup=symbol_lookup,
    )
    classification = classify_alert(
        binding=binding,
        **(classification_signals or {}),
    )
    metadata: PredicateMetadata = extract_predicate_metadata(
        rule_id=binding.rule_id,
        sarif_rule=alert.get("sarif_rule"),
    )
    examples, example_diags = get_predicate_examples(
        metadata=metadata, adapter=corpus_adapter, k=k
    )

    suppression: SuppressionProposal | None = None
    if classification.classification == ClassificationValue.LIKELY_FALSE_POSITIVE:
        suppression = propose_suppression(
            classification=classification,
            rule_id=binding.rule_id,
            file_path=binding.file_path,
            binding_confidence=binding.confidence,
        )

    repair_context: RepairContext | None = None
    patch: SASTPatch | None = None
    sandbox_result: SandboxResult | None = None
    analyser_result: AnalyserRerunResult | None = None
    sarif_delta_result: SARIFDeltaVerificationResult | None = None
    build_test_result: BuildTestResult | None = None
    patch_risk: dict[str, Any] | None = None
    remaining_notes: list[RemainingRiskNote] = []

    skip_repair = (
        suppression is not None
        and classification.classification == ClassificationValue.LIKELY_FALSE_POSITIVE
        and not generate_patch
    )

    if not skip_repair:
        repair_context = build_repair_context(
            binding=binding,
            classification=classification,
            metadata=metadata,
            examples=examples,
        )
        generator: PatchGeneratorInterface = patch_generator or NullPatchGenerator()
        patch = generator.generate(repair_context)

        manager = SandboxManager()
        try:
            if repo_root is not None:
                sandbox_result = manager.apply_patch(repo_root=repo_root, patch=patch)
            else:
                sandbox_result = SandboxResult(
                    alert_id=binding.alert_id,
                    sandbox_path=str(manager.sandbox_root),
                    patch_applied=True,
                    sandbox_snapshot_id="sb:no-repo",
                    cleanup_policy="always",
                )
            if null_mode and sandbox_result.patch_applied is False:
                sandbox_result = sandbox_result.model_copy(
                    update={"patch_applied": True, "apply_error": None}
                )
            analyser_result = await rerun_analyser(
                alert_id=binding.alert_id,
                sandbox=sandbox_result,
                analyser_id=analyser_id,
                analyser_version=analyser_version,
                runner=analyser_runner,
            )
            sarif_delta_result = verify_sarif_delta(
                alert_id=binding.alert_id,
                before_alerts=list(before_alerts or []),
                after_alerts=list(after_alerts or []),
                before_run_id=sarif_run_before_id,
                after_run_id=sarif_run_after_id,
            )
            build_test_result = await run_build_and_tests(
                alert_id=binding.alert_id,
                sandbox_path=sandbox_result.sandbox_path,
                sandbox_snapshot_id=sandbox_result.sandbox_snapshot_id,
                changed_files=patch.changed_files,
                coverage_map=coverage_map,
                runner=build_test_runner,
            )
        finally:
            manager.cleanup()

        if risk_classifier is not None:
            patch_risk = await risk_classifier(patch.diff_text, patch.changed_files)

        remaining_notes = generate_remaining_risk(
            alert_id=binding.alert_id,
            metadata=metadata,
            sarif_delta=sarif_delta_result,
            build_test=build_test_result,
            poc_plus_available=poc_plus_available,
            graph_dataflow_complete=graph_dataflow_complete,
        )

    verdict, success, recommendation = _decide_verdict(
        classification=classification,
        suppression=suppression,
        sarif_delta=sarif_delta_result,
        build_test=build_test_result,
        remaining_risk=remaining_notes,
    )

    sheet = default_harness_condition_sheet(
        run_id=run_id or "phase12-sast-repair-run",
        model_backend=(patch.generator_model if patch else "phase12-null-backend"),
        tool_set=("run_sast_repair", "get_predicate_examples"),
        permission_mode=permission_mode,
    )

    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(binding.diagnostics)
    diagnostics.extend(example_diags)
    if analyser_result and analyser_result.rerun_status == RerunStatus.UNAVAILABLE:
        diagnostics.append(
            {"code": "analyser_rerun_unavailable", "alert_id": binding.alert_id}
        )

    report = SASTRepairReport(
        report_id=_report_id(binding.alert_id),
        alert_id=binding.alert_id,
        run_id=run_id,
        harness_condition_id=sheet.hcs_id,
        alert_binding=binding,
        alert_classification=classification,
        predicate_metadata=metadata,
        predicate_examples=examples,
        repair_context=repair_context,
        patch=patch,
        suppression_proposal=suppression,
        sandbox_result=sandbox_result,
        analyser_rerun=analyser_result,
        sarif_delta=sarif_delta_result,
        build_test_result=build_test_result,
        patch_risk_result=patch_risk,
        remaining_risk_notes=remaining_notes,
        success=success,
        verdict=verdict,
        recommendation=recommendation,
        diagnostics=diagnostics,
    )
    return report, sheet


__all__ = [
    "run_sast_repair",
    "PatchRiskClassifier",
    # re-exports for downstream typing
    "AlertBinding",
    "BindingConfidence",
    "ClassificationConfidence",
]
