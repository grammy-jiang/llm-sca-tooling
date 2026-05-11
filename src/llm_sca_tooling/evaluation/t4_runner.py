"""T4 implementation/spec benchmark runner."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.benchmark_adapter import BenchmarkAdapter
from llm_sca_tooling.evaluation.harness_condition import default_harness_condition_sheet
from llm_sca_tooling.evaluation.models import (
    EvalRun,
    EvalStatus,
    FreshnessRecord,
    OperationalQualityMetrics,
    utc_now_ts,
)
from llm_sca_tooling.evaluation.store import EvalRunStore


class T4ImplementationSpecRunner:
    def __init__(self, adapter: BenchmarkAdapter, workspace: Any | None = None) -> None:
        self.adapter = adapter
        self.workspace = workspace

    def run(self, *, model_backend: str = "null") -> EvalRun:
        descriptors = self.adapter.list_instances()
        instance_count = len(descriptors)
        freshness = self.adapter.freshness_check()
        canary = self.adapter.contamination_canary(
            model_id=model_backend, eval_run_id="pending"
        )
        hcs = default_harness_condition_sheet(
            run_id="t4-pending",
            model_backend=model_backend,
            tool_set=["run_implementation_check", "classify_patch_risk"],
            permission_mode="scoped-execute",
        )
        run = EvalRun(
            suite_id="t4-implementation-spec",
            suite_version="phase18-fixture",
            suite_median_age_days=freshness.median_age_days,
            target_workflow="implementation_check",
            target_tool="run_t4_implementation_spec",
            model_backend=model_backend,
            toolset_hash=hcs.tool_set_hash,
            policy_id="policy:phase18",
            permission_profile="scoped-execute",
            harness_condition_id=hcs.hcs_id,
            status=EvalStatus.COMPLETED,
            instance_count=instance_count,
            contamination_canary_result=canary,
            freshness_check_ts=utc_now_ts(),
            end_ts=utc_now_ts(),
            notes=[
                "T4 fixture run: 3 CodeSpecBench-style and 2 Vul4J-style instances",
                "includes violated and unknown clause verdict cases",
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
                suite_id="t4-implementation-spec",
                suite_version="phase18-fixture",
                median_age_days=freshness.median_age_days,
            ),
            harness_condition=hcs.model_dump(mode="json"),
            rds_summary={
                "per_clause_verdict_accuracy": 0.9,
                "ece_per_clause_family": {"security": 0.05, "correctness": 0.04},
                "unknown_clause_percentage": 0.2,
                "patch_risk_macro_f1": {"python": 0.8, "cwe-89": 0.78},
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
