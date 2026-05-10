"""Eval-run replay helpers."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import EvalRun


def replay_eval_run(run: EvalRun) -> dict[str, object]:
    missing = []
    if run.instance_results_ref is None:
        missing.append("instance_results_ref")
    if run.aggregate_metrics_ref is None:
        missing.append("aggregate_metrics_ref")
    return {
        "eval_run_id": run.eval_run_id,
        "replayable": not missing,
        "missing_refs": missing,
    }
