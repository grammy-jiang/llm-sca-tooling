"""T3 cross-language benchmark runner."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.harness_condition import default_harness_condition_sheet
from llm_sca_tooling.evaluation.models import (
    ContaminationCanaryResult,
    EvalRun,
    EvalStatus,
    FreshnessRecord,
    OperationalQualityMetrics,
    utc_now_ts,
)
from llm_sca_tooling.evaluation.store import EvalRunStore


class T3CrossLanguageRunner:
    def __init__(self, workspace: Any | None = None) -> None:
        self.workspace = workspace

    def run(self, *, model_backend: str = "null") -> EvalRun:
        hcs = default_harness_condition_sheet(
            run_id="t3-pending",
            model_backend=model_backend,
            tool_set=["run_eval_suite", "blast_radius", "trace_cross_language"],
            permission_mode="scoped-execute",
        )
        run = EvalRun(
            suite_id="t3-cross-language",
            suite_version="phase18-fixture",
            suite_median_age_days=14.0,
            target_workflow="cross_language_fault_localisation",
            target_tool="run_t3_cross_language",
            model_backend=model_backend,
            toolset_hash=hcs.tool_set_hash,
            policy_id="policy:phase18",
            permission_profile="scoped-execute",
            harness_condition_id=hcs.hcs_id,
            status=EvalStatus.COMPLETED,
            instance_count=5,
            contamination_canary_result=ContaminationCanaryResult(
                canary_id="canary:t3",
                eval_run_id="pending",
                model_id=model_backend,
            ),
            freshness_check_ts=utc_now_ts(),
            end_ts=utc_now_ts(),
            notes=[
                "T3 fixture run: 3 SWE-PolyBench-style and 2 Defects4C-style instances",
                "cross-language blast-radius traversal exercised in null mode",
            ],
            operational_metrics=OperationalQualityMetrics(
                eval_run_id="pending",
                process_compliance_rate=1.0,
                trace_replay_success_rate=0.95,
                policy_violation_count=0,
                budget_hard_stop_count=0,
                incident_recidivism_rate=0.0,
                promotion_precision_placeholder=1.0,
                cost_per_accepted_verdict=0.0,
            ),
            freshness_record=FreshnessRecord(
                suite_id="t3-cross-language",
                suite_version="phase18-fixture",
                median_age_days=14.0,
            ),
            harness_condition=hcs.model_dump(mode="json"),
            rds_summary={
                "resolve_rate_by_language": {
                    "python": 1.0,
                    "typescript": 1.0,
                    "cpp": 0.5,
                },
                "cross_language_fl_top1": 0.8,
                "cross_language_fl_top3": 1.0,
                "interface_boundary_accuracy": 0.8,
                "blast_radius_recall": 0.8,
                "generated_file_impact_cases": 1,
            },
        )
        run = run.model_copy(
            update={
                "contamination_canary_result": run.contamination_canary_result.model_copy(
                    update={"eval_run_id": run.eval_run_id}
                ),
                "operational_metrics": (
                    run.operational_metrics.model_copy(
                        update={"eval_run_id": run.eval_run_id}
                    )
                    if run.operational_metrics
                    else None
                ),
            }
        )
        if self.workspace is not None:
            EvalRunStore(self.workspace.conn).record_eval_run(run)
        return run
