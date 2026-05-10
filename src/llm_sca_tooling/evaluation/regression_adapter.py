"""Prompt, manifest, and tool-description regression adapter."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import ManifestRegressionResult


def compare_manifest_snapshots(
    *,
    run_id: str,
    eval_run_id: str,
    scope: str,
    baseline: dict[str, object],
    current: dict[str, object],
) -> ManifestRegressionResult:
    findings = []
    changed: list[str] = []
    all_keys = sorted(set(baseline) | set(current))
    for key in all_keys:
        if key not in baseline:
            changed.append(key)
            findings.append(
                {"item": key, "classification": "compatible", "change": "added"}
            )
        elif key not in current:
            changed.append(key)
            findings.append(
                {"item": key, "classification": "breaking", "change": "removed"}
            )
        elif baseline[key] != current[key]:
            changed.append(key)
            classification = (
                "policy-relevant"
                if "permission" in key or "policy" in key
                else "unknown"
            )
            findings.append(
                {"item": key, "classification": classification, "change": "changed"}
            )
    verdict = "compatible"
    if any(item["classification"] == "breaking" for item in findings):
        verdict = "breaking"
    elif any(item["classification"] == "policy-relevant" for item in findings):
        verdict = "policy-relevant"
    elif findings:
        verdict = "unknown"
    return ManifestRegressionResult(
        run_id=run_id,
        eval_run_id=eval_run_id,
        scope=scope,
        changed_items=changed,
        findings=findings,
        overall_verdict=verdict,
    )
