"""DryRUN prediction contract."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    DiffRecord,
    DryRUNMismatch,
    DryRUNPrediction,
)


def make_dryrun_prediction(diff: DiffRecord) -> DryRUNPrediction:
    return DryRUNPrediction(
        diff_id=diff.diff_id,
        intended_behaviour_change="patch changes listed files",
        expected_files_changed=diff.changed_files,
        expected_test_cases_passing=["required"],
        expected_positive_cases=["patched path works"],
        expected_negative_cases=["old failing path no longer fails"],
        expected_edge_cases=["empty input"],
        predicted_outputs={"files_changed": len(diff.changed_files)},
        stated_invariants=["no new critical SARIF alerts", "required tests pass"],
        stated_risks=[],
    )


def compare_dryrun_actual(
    prediction: DryRUNPrediction, *, actual_files_changed: list[str]
) -> list[DryRUNMismatch]:
    mismatches: list[DryRUNMismatch] = []
    expected = set(prediction.expected_files_changed)
    actual = set(actual_files_changed)
    if actual - expected:
        mismatches.append(
            DryRUNMismatch(
                diff_id=prediction.diff_id,
                prediction_id=f"dryrun:{prediction.diff_id}",
                mismatch_type="extra_files_changed",
                predicted_value=sorted(expected),
                actual_value=sorted(actual),
                severity="medium",
                residual_risk_note="Patch changed files outside DryRUN expectation.",
            )
        )
    if expected - actual:
        mismatches.append(
            DryRUNMismatch(
                diff_id=prediction.diff_id,
                prediction_id=f"dryrun:{prediction.diff_id}",
                mismatch_type="fewer_files_changed",
                predicted_value=sorted(expected),
                actual_value=sorted(actual),
                severity="low",
                residual_risk_note="Patch touched fewer files than predicted.",
            )
        )
    return mismatches
