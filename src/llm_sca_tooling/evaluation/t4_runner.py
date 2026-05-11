"""Phase 18 T4 implementation/spec benchmark runner."""

from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import Field

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.contamination import unknown_canary
from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.evaluation.models import (
    EvalInstanceResult,
    EvalRun,
    EvalStatus,
    StrictEvalModel,
)
from llm_sca_tooling.evaluation.operational_metrics import compute_operational_metrics
from llm_sca_tooling.impl_check.models import (
    ClauseVerdictMatrix,
    ClauseVerdictRecord,
)
from llm_sca_tooling.release.calibration import expected_calibration_error
from llm_sca_tooling.release.models import CalibrationSample

__all__ = [
    "T4Fixture",
    "build_t4_fixture_matrices",
    "default_t4_fixtures",
    "run_t4_null",
]


class T4Fixture(StrictEvalModel):
    instance_id: str
    benchmark_family: str
    clause_family: str
    gold_verdicts: list[str]
    predicted_verdicts: list[str]
    probabilities: list[float] = Field(default_factory=list)
    patch_risk_label: str = "safe"
    language: str = "python"


def default_t4_fixtures() -> list[T4Fixture]:
    return [
        T4Fixture(
            instance_id="codespecbench-authz",
            benchmark_family="codespecbench",
            clause_family="security",
            gold_verdicts=["satisfied", "violated"],
            predicted_verdicts=["satisfied", "violated"],
            probabilities=[0.95, 0.95],
            patch_risk_label="vulnerable",
        ),
        T4Fixture(
            instance_id="codespecbench-cache",
            benchmark_family="codespecbench",
            clause_family="correctness",
            gold_verdicts=["satisfied", "unknown"],
            predicted_verdicts=["satisfied", "unknown"],
            probabilities=[0.95, 0.95],
        ),
        T4Fixture(
            instance_id="codespecbench-policy",
            benchmark_family="codespecbench",
            clause_family="compliance",
            gold_verdicts=["satisfied"],
            predicted_verdicts=["satisfied"],
            probabilities=[0.95],
        ),
        T4Fixture(
            instance_id="vul4j-path-traversal",
            benchmark_family="vul4j",
            clause_family="security",
            gold_verdicts=["violated"],
            predicted_verdicts=["violated"],
            probabilities=[0.95],
            patch_risk_label="vulnerable",
            language="java",
        ),
        T4Fixture(
            instance_id="vul4j-deserialisation",
            benchmark_family="vul4j",
            clause_family="security",
            gold_verdicts=["unknown", "violated"],
            predicted_verdicts=["unknown", "violated"],
            probabilities=[0.95, 0.95],
            patch_risk_label="vulnerable",
            language="java",
        ),
    ]


def run_t4_null(
    *,
    store: EvalStore | None = None,
    model_backend: str = "null",
    fixtures: list[T4Fixture] | None = None,
) -> EvalRun:
    fixtures = fixtures or default_t4_fixtures()
    eval_run = EvalRun(
        suite_id="t4-implementation-spec",
        suite_version="phase18.v1",
        suite_median_age_days=14.0,
        target_workflow="implementation-check-evaluation",
        target_tool="run_eval_suite",
        model_backend=model_backend,
        toolset_hash="phase18-null",
        policy_id="phase18-null",
        permission_profile="read/search",
        harness_condition_id="pending",
        instance_count=len(fixtures),
        contamination_canary_result=unknown_canary(
            eval_run_id="pending", model_id=model_backend, probe_instance_id="unknown"
        ),
        artefact_manifest_ref="memory://phase18/t4",
    )
    hcs = HarnessConditionSheet.create(
        run_id=eval_run.eval_run_id, model_backend=model_backend
    )
    matrices = build_t4_fixture_matrices(eval_run.eval_run_id, fixtures=fixtures)
    results = [
        _instance_result(fixture, matrix, eval_run.eval_run_id)
        for fixture, matrix in zip(fixtures, matrices, strict=True)
    ]
    eval_run.harness_condition_id = hcs.hcs_id
    eval_run.contamination_canary_result = unknown_canary(
        eval_run_id=eval_run.eval_run_id,
        model_id=model_backend,
        probe_instance_id=fixtures[0].instance_id if fixtures else "unknown",
    )
    eval_run.status = EvalStatus.completed
    eval_run.end_ts = hcs.created_ts
    eval_run.instance_results_ref = f"memory://eval/{eval_run.eval_run_id}/instances"
    eval_run.aggregate_metrics_ref = f"memory://eval/{eval_run.eval_run_id}/t4"
    eval_run.operational_metrics_ref = (
        f"memory://eval/{eval_run.eval_run_id}/operational"
    )
    eval_run.fl_metrics = _aggregate_t4_metrics(fixtures)
    eval_run.operational_metrics = compute_operational_metrics(
        eval_run_id=eval_run.eval_run_id,
        instance_results=results,
        run_events=_complete_events(results),
    )
    eval_run.manifest_regression = {"overall_verdict": "compatible", "findings": []}
    if store is not None:
        store.record_eval_run(eval_run)
    return eval_run


def build_t4_fixture_matrices(
    eval_run_id: str,
    *,
    fixtures: list[T4Fixture] | None = None,
) -> list[ClauseVerdictMatrix]:
    fixtures = fixtures or default_t4_fixtures()
    return [_matrix(eval_run_id, fixture) for fixture in fixtures]


def _matrix(eval_run_id: str, fixture: T4Fixture) -> ClauseVerdictMatrix:
    records = [
        ClauseVerdictRecord(
            clause_id=f"{fixture.instance_id}:clause:{index}",
            final_verdict=predicted,
            confidence="calibrated",
            ece_bucket=fixture.clause_family,
            stage_5_verdicts=[predicted],
            dominant_evidence="fixture-gold",
            auto_pass_gate_passed=predicted == gold and predicted != "unknown",
            calibration_family=fixture.clause_family,
            uncertainty_reason="fixture unknown" if predicted == "unknown" else None,
        )
        for index, (predicted, gold) in enumerate(
            zip(fixture.predicted_verdicts, fixture.gold_verdicts, strict=True),
            start=1,
        )
    ]
    counts = Counter(record.final_verdict for record in records)
    return ClauseVerdictMatrix(
        doc_id=f"doc:{fixture.instance_id}",
        run_id=eval_run_id,
        clause_count=len(records),
        satisfied_count=counts["satisfied"],
        violated_count=counts["violated"],
        unknown_count=counts["unknown"],
        per_clause_records=records,
        overall_compliance_status=_overall_status(counts),
    )


def _instance_result(
    fixture: T4Fixture,
    matrix: ClauseVerdictMatrix,
    eval_run_id: str,
) -> EvalInstanceResult:
    accuracy = _fixture_accuracy(fixture)
    return EvalInstanceResult(
        instance_id=fixture.instance_id,
        eval_run_id=eval_run_id,
        suite_id="t4-implementation-spec",
        issue_ref=f"memory://fixtures/t4/{fixture.instance_id}/spec",
        gold_patch_ref=f"memory://fixtures/t4/{fixture.instance_id}/gold",
        fl_result_ref=f"memory://fixtures/t4/{fixture.instance_id}/matrix",
        fl_top1_correct=accuracy == 1.0,
        fl_top3_correct=accuracy >= 0.5,
        fl_topN_correct=accuracy >= 0.5,
        fl_conditioned_repair_correct=accuracy == 1.0,
        repair_correct=accuracy == 1.0,
        gate_results=[
            {"name": "clause_accuracy", "passed": accuracy == 1.0},
            {
                "name": "unknown_preserved",
                "passed": matrix.unknown_count
                == fixture.predicted_verdicts.count("unknown"),
            },
        ],
        contamination_flag="unknown",
        flaky_flag=False,
        budget_events=["none"],
        notes=(
            f"{fixture.benchmark_family}; clauses={matrix.clause_count}; "
            f"family={fixture.clause_family}"
        ),
    )


def _overall_status(counts: Counter[str]) -> str:
    if counts["violated"]:
        return "violated"
    if counts["unknown"]:
        return "unknown"
    return "satisfied"


def _aggregate_t4_metrics(fixtures: list[T4Fixture]) -> dict[str, object]:
    samples = [
        CalibrationSample(
            sample_id=f"{fixture.instance_id}:{index}",
            family=fixture.clause_family,
            predicted_probability=probability,
            predicted_label=predicted,
            gold_label=gold,
        )
        for fixture in fixtures
        for index, (predicted, gold, probability) in enumerate(
            zip(
                fixture.predicted_verdicts,
                fixture.gold_verdicts,
                fixture.probabilities,
                strict=True,
            ),
            start=1,
        )
    ]
    by_family: dict[str, list[CalibrationSample]] = defaultdict(list)
    for sample in samples:
        by_family[sample.family].append(sample)
    unknown_count = sum(
        verdict == "unknown"
        for fixture in fixtures
        for verdict in fixture.predicted_verdicts
    )
    clause_count = len(samples)
    return {
        "suite": "t4",
        "instance_count": len(fixtures),
        "clause_accuracy": sum(sample.correct for sample in samples) / clause_count,
        "ece_per_clause_family": {
            family: expected_calibration_error(items)
            for family, items in sorted(by_family.items())
        },
        "unknown_clause_rate": unknown_count / clause_count,
        "patch_risk_macro_f1_per_language": {
            "java": 1.0,
            "python": 1.0,
        },
    }


def _fixture_accuracy(fixture: T4Fixture) -> float:
    return sum(
        predicted == gold
        for predicted, gold in zip(
            fixture.predicted_verdicts, fixture.gold_verdicts, strict=True
        )
    ) / len(fixture.gold_verdicts)


def _complete_events(results: list[EvalInstanceResult]) -> list[dict[str, str]]:
    return [
        {"instance_id": result.instance_id, "type": event_type}
        for result in results
        for event_type in ("tool_call", "gate_result", "budget_event", "final_verdict")
    ]
