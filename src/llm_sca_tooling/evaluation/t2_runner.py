"""T2 regression runner."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.benchmark_adapter import BenchmarkAdapter
from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    default_harness_condition_sheet,
)
from llm_sca_tooling.evaluation.models import (
    EvalRun,
    EvalStatus,
    ManifestRegressionResult,
    OperationalQualityMetrics,
    new_eval_run_id,
    utc_now_ts,
)
from llm_sca_tooling.evaluation.regression_adapter import compare_manifest_snapshots
from llm_sca_tooling.evaluation.store import EvalRunStore


class T2RegressionRunner:
    def __init__(self, adapter: BenchmarkAdapter, workspace: Any | None = None) -> None:
        self.adapter = adapter
        self.workspace = workspace

    def run(
        self,
        *,
        baseline: EvalRun | None = None,
        model_backend: str = "null",
        policy_id: str = "policy:phase10-null",
        permission_profile: str = "scoped-execute",
        null_mode: bool = True,
        harness_condition: HarnessConditionSheet | None = None,
    ) -> EvalRun:
        descriptors = self.adapter.list_instances()
        instance_count = len(descriptors)
        hcs = harness_condition or default_harness_condition_sheet(
            run_id="t2-pending",
            model_backend=model_backend,
            tool_set=["run_eval_suite", "run_patch_review", "run_issue_resolution"],
            permission_mode=permission_profile,
        )
        freshness = self.adapter.freshness_check()
        canary = self.adapter.contamination_canary(
            model_id=model_backend,
            eval_run_id="pending",
        )
        manifest_regression: ManifestRegressionResult | None = None
        if baseline is not None:
            baseline_snap: dict[str, object] = {
                "suite_id": baseline.suite_id,
                "suite_version": baseline.suite_version,
                "instance_count": str(baseline.instance_count),
                "top1_rate": str(
                    baseline.aggregate_metrics.top1_rate
                    if baseline.aggregate_metrics
                    else None
                ),
                "repair_rate": str(
                    baseline.aggregate_metrics.repair_rate
                    if baseline.aggregate_metrics
                    else None
                ),
            }
            current_snap: dict[str, object] = {
                "suite_id": self.adapter.suite_id,
                "suite_version": self.adapter.suite_version,
                "instance_count": str(instance_count),
                "top1_rate": "null",
                "repair_rate": "null",
            }
            tmp_id = new_eval_run_id()
            manifest_regression = compare_manifest_snapshots(
                run_id="t2-regression",
                eval_run_id=tmp_id,
                scope="benchmark_regression",
                baseline=baseline_snap,
                current=current_snap,
            )
        regression_gate_status = (
            "compatible"
            if manifest_regression is None
            else manifest_regression.overall_verdict
        )
        run = EvalRun(
            suite_id=self.adapter.suite_id,
            suite_version=self.adapter.suite_version,
            suite_median_age_days=freshness.median_age_days,
            target_workflow="regression_check",
            target_tool="run_eval_suite",
            model_backend=model_backend,
            toolset_hash=hcs.tool_set_hash,
            policy_id=policy_id,
            permission_profile=permission_profile,
            harness_condition_id=hcs.hcs_id,
            status=EvalStatus.COMPLETED,
            instance_count=instance_count,
            contamination_canary_result=canary,
            freshness_check_ts=utc_now_ts(),
            end_ts=utc_now_ts(),
            manifest_regression=manifest_regression,
            notes=[
                f"T2 regression run: {instance_count} instances from {self.adapter.suite_id!r}",
                "null_mode=True: no real execution" if null_mode else "live mode",
                f"regression gate: {regression_gate_status}",
            ],
            operational_metrics=OperationalQualityMetrics(
                eval_run_id="pending",
                process_compliance_rate=1.0,
                trace_replay_success_rate=0.0,
                policy_violation_count=0,
                budget_hard_stop_count=0,
                incident_recidivism_rate=0.0,
                promotion_precision_placeholder=0.0,
            ),
            freshness_record=freshness,
            harness_condition=hcs.model_dump(mode="json"),
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
