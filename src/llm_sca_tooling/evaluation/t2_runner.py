"""T2 regression runner skeleton and Phase 18 tier status helpers."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.evaluation.models import StrictEvalModel, now_ts

__all__ = ["RegressionVerdict", "run_t2_skeleton", "run_tier_stub"]


class RegressionVerdict(StrictEvalModel):
    suite: str
    status: str
    verdict: str
    baseline_eval_run_id: str | None = None
    current_eval_run_id: str | None = None
    freshness_warning: str | None = None
    notes: list[str] = Field(default_factory=list)
    computed_ts: str = Field(default_factory=now_ts)


def run_t2_skeleton(
    *,
    current_eval_run_id: str,
    baseline_eval_run_id: str | None = None,
    suite_median_age_days: float = 0.0,
    freshness_threshold_days: float = 30.0,
) -> RegressionVerdict:
    warning = (
        f"suite median age {suite_median_age_days} exceeds {freshness_threshold_days}"
        if suite_median_age_days > freshness_threshold_days
        else None
    )
    return RegressionVerdict(
        suite="t2",
        status="completed",
        verdict="inconclusive" if baseline_eval_run_id is None else "equal",
        baseline_eval_run_id=baseline_eval_run_id,
        current_eval_run_id=current_eval_run_id,
        freshness_warning=warning,
        notes=["Phase 10 skeleton only"],
    )


def run_tier_stub(suite: str) -> RegressionVerdict:
    if suite not in {"t3", "t4"}:
        raise ValueError(f"unsupported stub suite: {suite}")
    return RegressionVerdict(
        suite=suite,
        status="implemented_in_phase_18",
        verdict="available",
        notes=["Use run_t3_null or run_t4_null for deterministic local execution"],
    )
