"""Harness ablation report assembly."""

from __future__ import annotations

from llm_sca_tooling.release.models import (
    AblationConfig,
    AblationControlChange,
    AblationDelta,
    AblationReport,
    ReleaseImpact,
)

__all__ = [
    "build_ablation_report",
    "classify_ablation_delta",
    "required_ablation_configs",
]


def required_ablation_configs(baseline_config_ref: str) -> list[AblationConfig]:
    controls = [
        ("permissions_narrowed", "path_allowlist=repo", "path_allowlist=single_repo"),
        ("permissions_widened", "execute=scoped", "execute=all_paths"),
        ("sarif_gate_disabled", "sarif_gate=on", "sarif_gate=off"),
        (
            "maintainability_gate_disabled",
            "maintainability_gate=on",
            "maintainability_gate=off",
        ),
        ("memory_disabled", "memory=weighted", "memory=zero_weight"),
        (
            "memory_enabled_unshipped",
            "memory=gate_bound",
            "memory=unshipped_enabled",
        ),
        ("compaction_aggressive", "eviction=standard", "eviction=aggressive"),
        ("prompt_variant_A", "prompt=release", "prompt=variant_A"),
    ]
    return [
        AblationConfig(
            ablation_id=name,
            baseline_config_ref=baseline_config_ref,
            modified_controls=[
                AblationControlChange(
                    control_name=name,
                    before_value=before,
                    after_value=after,
                )
            ],
            rationale=f"Measure release impact of {name}.",
        )
        for name, before, after in controls
    ]


def classify_ablation_delta(
    *,
    ablation_id: str,
    resolve_rate_delta: float,
    policy_compliance_delta: float,
    trace_replay_delta: float,
) -> ReleaseImpact:
    operational_regressed = policy_compliance_delta < 0 or trace_replay_delta < 0
    if resolve_rate_delta > 0 and operational_regressed:
        return ReleaseImpact.unexpected_improvement
    if resolve_rate_delta < 0:
        expected_loss_controls = {
            "sarif_gate_disabled",
            "maintainability_gate_disabled",
            "memory_disabled",
            "compaction_aggressive",
        }
        if ablation_id in expected_loss_controls:
            return ReleaseImpact.expected_degradation
        return ReleaseImpact.unexpected_degradation
    if operational_regressed:
        return ReleaseImpact.unexpected_degradation
    return ReleaseImpact.no_impact


def build_ablation_report(
    *,
    baseline_eval_run_id: str,
    baseline_metrics: dict[str, float],
    ablation_configs: list[AblationConfig],
    ablation_eval_run_ids: list[str],
    ablation_metrics: dict[str, dict[str, float]],
) -> AblationReport:
    deltas: list[AblationDelta] = []
    for config, eval_run_id in zip(
        ablation_configs, ablation_eval_run_ids, strict=True
    ):
        metrics = ablation_metrics[eval_run_id]
        resolve_delta = metrics.get("resolve_rate", 0.0) - baseline_metrics.get(
            "resolve_rate", 0.0
        )
        policy_delta = metrics.get(
            "policy_compliance_rate", 0.0
        ) - baseline_metrics.get("policy_compliance_rate", 0.0)
        trace_delta = metrics.get(
            "trace_replay_success_rate", 0.0
        ) - baseline_metrics.get("trace_replay_success_rate", 0.0)
        impact = classify_ablation_delta(
            ablation_id=config.ablation_id,
            resolve_rate_delta=resolve_delta,
            policy_compliance_delta=policy_delta,
            trace_replay_delta=trace_delta,
        )
        deltas.append(
            AblationDelta(
                ablation_id=config.ablation_id,
                resolve_rate_delta=resolve_delta,
                policy_compliance_delta=policy_delta,
                trace_replay_delta=trace_delta,
                release_impact=impact,
                investigation_note=(
                    "Investigate before release."
                    if impact
                    in {
                        ReleaseImpact.unexpected_improvement,
                        ReleaseImpact.unexpected_degradation,
                    }
                    else None
                ),
            )
        )
    release_impact = _rollup_impact(deltas)
    return AblationReport(
        baseline_eval_run_id=baseline_eval_run_id,
        ablation_configs=ablation_configs,
        ablation_eval_run_ids=ablation_eval_run_ids,
        per_ablation_delta=deltas,
        summary_findings=[
            f"{delta.ablation_id}: {delta.release_impact.value}" for delta in deltas
        ],
        release_impact=release_impact,
    )


def _rollup_impact(deltas: list[AblationDelta]) -> ReleaseImpact:
    impacts = {delta.release_impact for delta in deltas}
    if ReleaseImpact.unexpected_improvement in impacts:
        return ReleaseImpact.unexpected_improvement
    if ReleaseImpact.unexpected_degradation in impacts:
        return ReleaseImpact.unexpected_degradation
    if ReleaseImpact.expected_degradation in impacts:
        return ReleaseImpact.expected_degradation
    return ReleaseImpact.no_impact
