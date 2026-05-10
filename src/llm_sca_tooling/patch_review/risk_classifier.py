"""Patch-risk classifier interface with calibration gate.

Phase 11 ships a deterministic-only path: when no trained classifier is
calibrated for the patch's language and rule family, the deterministic
policy is used unconditionally. A trained classifier can be plugged in
later via :class:`TrainedClassifier`; until macro-F1 ≥ 0.75 and ECE ≤ 0.10
on the calibration family it is logged as advisory and never used to
gate merge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llm_sca_tooling.patch_review.models import (
    PatchRiskFeatureVector,
    PatchRiskResult,
    RiskClassValue,
)
from llm_sca_tooling.patch_review.risk_policy import apply_deterministic_policy

MIN_MACRO_F1 = 0.75
MAX_ECE = 0.10


class TrainedClassifier:
    """Placeholder for a trained patch-risk classifier."""

    def __init__(
        self,
        *,
        version: str,
        calibration_family: str,
        macro_f1: float,
        ece: float,
        predict_fn: Callable[[PatchRiskFeatureVector], PatchRiskResult],
    ) -> None:
        self.version = version
        self.calibration_family = calibration_family
        self.macro_f1 = macro_f1
        self.ece = ece
        self._predict = predict_fn

    @property
    def calibration_passed(self) -> bool:
        return self.macro_f1 >= MIN_MACRO_F1 and self.ece <= MAX_ECE

    def predict(self, feature_vector: PatchRiskFeatureVector) -> PatchRiskResult:
        return self._predict(feature_vector)


def classify(
    feature_vector: PatchRiskFeatureVector,
    *,
    sarif_delta: Any = None,
    test_delta: Any = None,
    interface_compat: Any = None,
    scope_audit: Any = None,
    maintainability: Any = None,
    required_tests: list[str] | None = None,
    poc_required: bool = False,
    calibration_family: str | None = None,
    trained_classifier: TrainedClassifier | None = None,
) -> PatchRiskResult:
    """Classify a patch by combining deterministic policy with optional trained model.

    Hard rules from the deterministic policy always apply first. The trained
    classifier may refine ``calibrated_probability`` and ``ece_bucket`` only
    when its calibration gate is met. ``unknown`` is returned when the
    deterministic rule-table also resolves to ``unknown`` and the classifier
    is unavailable for this calibration family.
    """
    deterministic = apply_deterministic_policy(
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

    if (
        trained_classifier is None
        or not trained_classifier.calibration_passed
        or trained_classifier.calibration_family != calibration_family
    ):
        if trained_classifier is not None:
            return deterministic.model_copy(
                update={
                    "active_overrides": [
                        *deterministic.active_overrides,
                        "classifier_calibration_below_threshold",
                    ]
                }
            )
        if (
            calibration_family is None
            and deterministic.risk_class == RiskClassValue.SAFE
        ):
            return deterministic.model_copy(
                update={
                    "active_overrides": [
                        *deterministic.active_overrides,
                        "calibration_family_missing",
                    ]
                }
            )
        return deterministic

    classifier_result = trained_classifier.predict(feature_vector)
    if deterministic.risk_class != RiskClassValue.SAFE:
        return deterministic
    return classifier_result.model_copy(
        update={
            "calibration_family": calibration_family,
            "classifier_version": trained_classifier.version,
        }
    )
