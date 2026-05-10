"""DryRUN prediction contract and mismatch detector."""

from __future__ import annotations

import hashlib
from typing import Any

from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    DiffRecord,
    DryRUNMismatch,
    DryRUNPrediction,
    MismatchType,
    TestDeltaRecord,
)


class NullDryRUNGenerator:
    """Deterministic fallback DryRUN generator for tests and offline runs.

    Predicts that the changed-file set in the diff is exactly the changed
    set, with no additional invariants or side effects. The mismatch
    detector therefore reports differences between this prediction and
    the actual outcomes.
    """

    name = "null-adapter"

    def predict(
        self,
        diff: DiffRecord,
        *,
        intended_behaviour_change: str | None = None,
    ) -> DryRUNPrediction:
        digest = hashlib.sha256(diff.diff_id.encode("utf-8")).hexdigest()
        return DryRUNPrediction(
            prediction_id=f"dryrun:{digest[:24]}",
            diff_id=diff.diff_id,
            intended_behaviour_change=intended_behaviour_change or "",
            expected_files_changed=list(diff.changed_files),
            expected_test_cases_passing=[],
            expected_test_cases_failing=[],
            expected_positive_cases=[],
            expected_negative_cases=[],
            expected_edge_cases=[],
            predicted_outputs=[],
            predicted_side_effects=[],
            stated_invariants=[],
            stated_risks=[],
            generator=self.name,
            confidence=ConfidenceLevel.HEURISTIC,
        )


def detect_dryrun_mismatches(
    prediction: DryRUNPrediction,
    *,
    actual_files_changed: list[str] | None = None,
    test_delta: TestDeltaRecord | None = None,
    actual_side_effects: list[str] | None = None,
    invariants_violated: list[str] | None = None,
    risks_materialised: list[str] | None = None,
) -> list[DryRUNMismatch]:
    mismatches: list[DryRUNMismatch] = []
    actual_files = actual_files_changed if actual_files_changed is not None else None
    if actual_files is not None:
        predicted = set(prediction.expected_files_changed)
        actual = set(actual_files)
        extra = sorted(actual - predicted)
        fewer = sorted(predicted - actual)
        if extra:
            mismatches.append(
                DryRUNMismatch(
                    diff_id=prediction.diff_id,
                    prediction_id=prediction.prediction_id,
                    mismatch_type=MismatchType.EXTRA_FILES_CHANGED,
                    predicted_value={"files": sorted(predicted)},
                    actual_value={"files": sorted(actual)},
                    severity="medium",
                    residual_risk_note=f"unexpected files: {extra}",
                )
            )
        if fewer:
            mismatches.append(
                DryRUNMismatch(
                    diff_id=prediction.diff_id,
                    prediction_id=prediction.prediction_id,
                    mismatch_type=MismatchType.FEWER_FILES_CHANGED,
                    predicted_value={"files": sorted(predicted)},
                    actual_value={"files": sorted(actual)},
                    severity="low",
                    residual_risk_note=f"missing files: {fewer}",
                )
            )

    if test_delta is not None:
        for tid in test_delta.newly_failing:
            if tid in prediction.expected_test_cases_passing:
                mismatches.append(
                    DryRUNMismatch(
                        diff_id=prediction.diff_id,
                        prediction_id=prediction.prediction_id,
                        mismatch_type=MismatchType.UNEXPECTED_TEST_FAILURE,
                        predicted_value={"test_id": tid, "expected": "passed"},
                        actual_value={"test_id": tid, "observed": "failed"},
                        severity="high",
                        residual_risk_note=f"test {tid} failed but was expected to pass",
                    )
                )
        for tid in test_delta.newly_passing:
            if tid in prediction.expected_test_cases_failing:
                mismatches.append(
                    DryRUNMismatch(
                        diff_id=prediction.diff_id,
                        prediction_id=prediction.prediction_id,
                        mismatch_type=MismatchType.UNEXPECTED_TEST_PASS,
                        predicted_value={"test_id": tid, "expected": "failed"},
                        actual_value={"test_id": tid, "observed": "passed"},
                        severity="medium",
                        residual_risk_note=f"test {tid} passed but was expected to fail",
                    )
                )

    for effect in actual_side_effects or []:
        if effect not in prediction.predicted_side_effects:
            mismatches.append(
                DryRUNMismatch(
                    diff_id=prediction.diff_id,
                    prediction_id=prediction.prediction_id,
                    mismatch_type=MismatchType.UNEXPECTED_SIDE_EFFECT,
                    predicted_value={"side_effects": prediction.predicted_side_effects},
                    actual_value={"side_effect": effect},
                    severity="medium",
                    residual_risk_note=f"unexpected side effect: {effect}",
                )
            )

    for inv in invariants_violated or []:
        mismatches.append(
            DryRUNMismatch(
                diff_id=prediction.diff_id,
                prediction_id=prediction.prediction_id,
                mismatch_type=MismatchType.INVARIANT_VIOLATED,
                predicted_value={"invariant": inv, "expected": "held"},
                actual_value={"invariant": inv, "observed": "violated"},
                severity="high",
                residual_risk_note=f"invariant violated: {inv}",
            )
        )

    for risk in risks_materialised or []:
        if risk in prediction.stated_risks:
            mismatches.append(
                DryRUNMismatch(
                    diff_id=prediction.diff_id,
                    prediction_id=prediction.prediction_id,
                    mismatch_type=MismatchType.STATED_RISK_MATERIALISED,
                    predicted_value={"risk": risk, "stated": True},
                    actual_value={"risk": risk, "materialised": True},
                    severity="high",
                    residual_risk_note=f"stated risk materialised: {risk}",
                )
            )

    return mismatches


def degraded_confidence(
    mismatches: list[DryRUNMismatch], current: ConfidenceLevel
) -> ConfidenceLevel:
    """DryRUN mismatches degrade confidence, never block merge directly."""
    if not mismatches:
        return current
    has_invariant = any(
        m.mismatch_type == MismatchType.INVARIANT_VIOLATED for m in mismatches
    )
    if has_invariant:
        return ConfidenceLevel.UNKNOWN
    if current == ConfidenceLevel.ANALYSER:
        return ConfidenceLevel.HEURISTIC
    return current


def _ensure_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("expected list")
    return [str(v) for v in value]
