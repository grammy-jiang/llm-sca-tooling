"""Prompt, manifest, and tool-description regression adapter."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import ManifestRegressionResult

__all__ = ["compare_snapshots"]


def compare_snapshots(
    *,
    run_id: str,
    eval_run_id: str,
    scope: str,
    baseline: dict[str, dict[str, object]],
    current: dict[str, dict[str, object]],
) -> ManifestRegressionResult:
    findings: list[dict[str, str]] = []
    changed: list[str] = []
    for name in sorted(set(baseline) | set(current)):
        if name not in baseline:
            changed.append(name)
            findings.append(
                {"item": name, "classification": "compatible", "reason": "added"}
            )
        elif name not in current:
            changed.append(name)
            findings.append(
                {"item": name, "classification": "breaking", "reason": "removed"}
            )
        elif baseline[name] != current[name]:
            changed.append(name)
            classification = (
                "policy-relevant"
                if baseline[name].get("permission") != current[name].get("permission")
                else "compatible"
            )
            findings.append(
                {"item": name, "classification": classification, "reason": "changed"}
            )
    verdict = (
        "breaking"
        if any(f["classification"] == "breaking" for f in findings)
        else (
            "policy-relevant"
            if any(f["classification"] == "policy-relevant" for f in findings)
            else "compatible"
        )
    )
    return ManifestRegressionResult(
        run_id=run_id,
        eval_run_id=eval_run_id,
        scope=scope,
        changed_items=changed,
        findings=findings,
        overall_verdict=verdict,
    )
