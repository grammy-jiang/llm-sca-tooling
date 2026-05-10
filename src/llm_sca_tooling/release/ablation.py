"""Harness ablation reporting."""

from __future__ import annotations

import uuid

from llm_sca_tooling.release.models import (
    AblationConfig,
    AblationReport,
    ReleaseImpact,
)
from llm_sca_tooling.schemas.base import JsonObject


def build_ablation_report(
    *,
    baseline_eval_run_id: str,
    configs: list[AblationConfig],
    ablation_eval_run_ids: list[str],
    deltas: dict[str, JsonObject],
) -> AblationReport:
    impact = ReleaseImpact.NO_IMPACT
    findings: list[str] = []
    for ablation_id, delta in deltas.items():
        resolve_delta = float(delta.get("resolve_rate_delta", 0.0))
        operational_delta = float(delta.get("operational_gate_delta", 0.0))
        if resolve_delta > 0 and operational_delta < 0:
            impact = ReleaseImpact.UNEXPECTED_IMPROVEMENT
            findings.append(
                f"{ablation_id}: resolve improved while operations degraded"
            )
        elif resolve_delta < 0:
            impact = ReleaseImpact.EXPECTED_DEGRADATION
            findings.append(f"{ablation_id}: expected degradation observed")
    return AblationReport(
        report_id=f"ablation:{uuid.uuid4().hex}",
        baseline_eval_run_id=baseline_eval_run_id,
        ablation_configs=configs,
        ablation_eval_run_ids=ablation_eval_run_ids,
        per_ablation_delta=deltas,
        summary_findings=findings,
        release_impact=impact,
    )
