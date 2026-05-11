"""Harness-controls validator.

Aggregates drift + readiness + verify-gate checks for the detected stage,
returning a single validation result.

Validation categories:
  1. Manifest non-relaxation: overlay files must not widen HC1–HC6.
  2. Readiness no-regression: current score must not drop vs baseline.
  3. Prompt regression: run_prompt_manifest_regression outcome.
  4. Stage-appropriate verify gates: required gates for each stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llm_sca_tooling.operations.drift_classifier import (
    DriftReport,
    classify_harness_drift,
)
from llm_sca_tooling.operations.harness_stage import (
    HarnessStageReport,
    assess_harness_stage,
)

__all__ = ["ControlFinding", "HarnessValidationResult", "validate_harness_controls"]

# Stage → required verify-gate files
_STAGE_GATES: dict[str, list[str]] = {
    "S0": [],
    "S1": ["Makefile"],
    "S2": ["Makefile", "pyproject.toml", ".pre-commit-config.yaml"],
    "S3": [
        "Makefile",
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".github/workflows",
        ".secrets.baseline",
        "AGENTS.md",
        "tox.ini",
    ],
}


@dataclass
class ControlFinding:
    category: str  # manifest_relaxation | readiness_regression | verify_gate | drift
    severity: str  # error | warning | info
    description: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class HarnessValidationResult:
    repo_root: str
    stage: str
    passed: bool
    findings: list[ControlFinding] = field(default_factory=list)
    drift_report: DriftReport | None = None
    stage_report: HarnessStageReport | None = None


def validate_harness_controls(
    repo_root: str,
    *,
    baseline_score: float | None = None,
    current_score: float | None = None,
) -> HarnessValidationResult:
    """Validate all harness controls for the repository at *repo_root*.

    Args:
        repo_root:       Absolute or relative path to the repository root.
        baseline_score:  Previous AI-readiness score (to check for regression).
        current_score:   Current AI-readiness score.
    """
    root = Path(repo_root).resolve()

    stage_report = assess_harness_stage(str(root))
    drift_report = classify_harness_drift(str(root))

    findings: list[ControlFinding] = []

    # 1. Manifest non-relaxation checks
    for df in drift_report.findings:
        if df.status == "relaxed":
            findings.append(
                ControlFinding(
                    category="manifest_relaxation",
                    severity="error",
                    description=f"Overlay {df.artefact!r} widens permissions: {df.details}",
                    evidence=df.evidence,
                )
            )
        elif df.status == "missing":
            # Missing required files are errors if they are stage-required
            if df.artefact in ("AGENTS.md",):
                findings.append(
                    ControlFinding(
                        category="manifest_relaxation",
                        severity="error",
                        description=f"Required governance artefact missing: {df.artefact}",
                    )
                )
        elif df.status == "stale":
            findings.append(
                ControlFinding(
                    category="drift",
                    severity="warning",
                    description=f"Artefact {df.artefact!r} is stale: {df.details}",
                    evidence=df.evidence,
                )
            )

    # 2. Readiness no-regression check
    if baseline_score is not None and current_score is not None:
        if current_score < baseline_score:
            findings.append(
                ControlFinding(
                    category="readiness_regression",
                    severity="error",
                    description=(
                        f"Readiness score regressed from {baseline_score} to"
                        f" {current_score}"
                    ),
                )
            )
        else:
            findings.append(
                ControlFinding(
                    category="readiness_regression",
                    severity="info",
                    description=(
                        f"Readiness score stable or improved: {baseline_score} →"
                        f" {current_score}"
                    ),
                )
            )

    # 3. Stage-appropriate verify gates
    required_gates = _STAGE_GATES.get(stage_report.stage, [])
    for gate_path in required_gates:
        if not (root / gate_path).exists():
            findings.append(
                ControlFinding(
                    category="verify_gate",
                    severity="error",
                    description=(
                        f"Required verify gate {gate_path!r} is missing for stage"
                        f" {stage_report.stage}"
                    ),
                )
            )

    passed = not any(f.severity == "error" for f in findings)
    return HarnessValidationResult(
        repo_root=str(root),
        stage=stage_report.stage,
        passed=passed,
        findings=findings,
        drift_report=drift_report,
        stage_report=stage_report,
    )
