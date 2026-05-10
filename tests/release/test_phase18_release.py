from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app
from llm_sca_tooling.evaluation.store import EvalRunStore
from llm_sca_tooling.evaluation.t3_runner import T3CrossLanguageRunner
from llm_sca_tooling.evaluation.t4_runner import T4ImplementationSpecRunner
from llm_sca_tooling.mcp_server.resources.eval import EvalResource
from llm_sca_tooling.release.ablation import build_ablation_report
from llm_sca_tooling.release.adversarial import run_adversarial_suite
from llm_sca_tooling.release.calibration import (
    build_calibration_report,
    expected_calibration_error,
)
from llm_sca_tooling.release.models import (
    AblationConfig,
    AblationControlChange,
    ReleaseImpact,
)
from llm_sca_tooling.release.operational_gates import compute_operational_harness_gate
from llm_sca_tooling.release.production_refresh import build_production_refresh_record
from llm_sca_tooling.release.release_gate import run_release_gate
from llm_sca_tooling.release.report_templates import (
    missing_report_sections,
    render_release_report,
)
from llm_sca_tooling.storage.workspace import initialize_workspace


def test_t3_t4_runners_store_eval_resources(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    t3 = T3CrossLanguageRunner(workspace).run()
    t4 = T4ImplementationSpecRunner(workspace).run()
    store = EvalRunStore(workspace.conn)
    assert store.get_eval_run(t3.eval_run_id).suite_id == "t3-cross-language"
    assert store.get_eval_run(t4.eval_run_id).suite_id == "t4-implementation-spec"
    ctx = type("Ctx", (), {"workspace": workspace})()
    resource = EvalResource().read(
        ctx,
        f"code-intelligence://eval/{t3.eval_run_id}",
        type("Parsed", (), {"segments": [t3.eval_run_id]})(),
    )
    assert resource.payload["eval_run"]["suite_id"] == "t3-cross-language"


def test_calibration_report_and_ece_thresholds() -> None:
    predictions = [
        {"confidence": 1.0, "correct": True, "label": "safe", "predicted": "safe"},
        {"confidence": 1.0, "correct": True, "label": "risky", "predicted": "risky"},
    ]
    assert expected_calibration_error(predictions) == 0.0
    report = build_calibration_report(
        eval_run_id="eval:1",
        model_backend="null",
        harness_condition_id="hcs:1",
        patch_risk_predictions=predictions,
        impl_check_predictions_by_family={"security": predictions},
        repo_qa_file_loc_accuracy=0.91,
        repo_qa_behaviour_tracing_accuracy=0.70,
        memory_delta_pp=3.0,
    )
    assert report.patch_risk_gate_passed is True
    assert report.impl_check_gate_passed is True
    assert report.memory_ship_gate_passed is True
    assert report.model_validate_json(report.model_dump_json()) == report


def test_ablation_detects_unexpected_improvement() -> None:
    with pytest.raises(ValueError):
        AblationConfig(
            ablation_id="bad",
            baseline_config_ref="base",
            modified_controls=[
                AblationControlChange(
                    control_name="a", before_value="1", after_value="2"
                ),
                AblationControlChange(
                    control_name="b", before_value="1", after_value="2"
                ),
            ],
            rationale="bad",
        )
    config = AblationConfig(
        ablation_id="permissions_widened",
        baseline_config_ref="base",
        modified_controls=[
            AblationControlChange(
                control_name="permissions", before_value="narrow", after_value="wide"
            )
        ],
        rationale="test control contribution",
    )
    report = build_ablation_report(
        baseline_eval_run_id="eval:base",
        configs=[config],
        ablation_eval_run_ids=["eval:ablation"],
        deltas={
            "permissions_widened": {
                "resolve_rate_delta": 0.05,
                "operational_gate_delta": -0.10,
            }
        },
    )
    assert report.release_impact is ReleaseImpact.UNEXPECTED_IMPROVEMENT


def test_operational_gate_computes_failures() -> None:
    result = compute_operational_harness_gate(
        eval_run_id="eval:1",
        records=[
            {
                "trace_complete": False,
                "policy_violation": True,
                "budget_hard_stop": True,
                "maintainability_pass": False,
                "manifest_regression_pass": False,
                "readiness_threshold_met": False,
                "open_p0_p1": True,
            }
        ],
    )
    assert result.gate_passed is False
    assert "manifest_regression" in result.failing_gates
    assert result.policy_violation_count == 1


def test_adversarial_suite_has_six_passing_checks() -> None:
    results = run_adversarial_suite()
    assert len(results) == 6
    assert all(result.passed for result in results)


def test_production_refresh_hides_gold_patch_and_requires_approval() -> None:
    record = build_production_refresh_record(
        source_run_id="run:1",
        issue_text_hash="hash:issue",
        repo_id="repo:1",
        fail_to_pass_tests_present=True,
        pass_to_pass_tests_present=True,
        test_relevance_validated=True,
        flaky_flag=False,
        approved=True,
        suite_id="t3-live",
    )
    assert record.gold_patch_hidden is True
    assert record.added_to_suite_id == "t3-live"


def test_release_gate_passes_and_fails() -> None:
    calibration = build_calibration_report(
        eval_run_id="eval:1",
        model_backend="null",
        harness_condition_id="hcs:1",
        patch_risk_predictions=[
            {"confidence": 1.0, "correct": True, "label": "safe", "predicted": "safe"}
        ],
        impl_check_predictions_by_family={
            "security": [
                {"confidence": 1.0, "correct": True, "label": "ok", "predicted": "ok"}
            ]
        },
        repo_qa_file_loc_accuracy=0.91,
        repo_qa_behaviour_tracing_accuracy=0.70,
        memory_delta_pp=3.0,
    )
    operational = compute_operational_harness_gate(
        eval_run_id="eval:1", records=[{"trace_complete": True}]
    )
    passed = run_release_gate(
        harness_condition_id="hcs:1",
        benchmark_results={"t3": {"passed": True}},
        calibration_report=calibration,
        operational_gate=operational,
        adversarial_results=run_adversarial_suite(),
    )
    assert passed.overall_pass is True
    failed = run_release_gate(
        harness_condition_id="hcs:1",
        benchmark_results={"t3": {"passed": False}},
        calibration_report=calibration,
        operational_gate=operational,
        adversarial_results=run_adversarial_suite(),
    )
    assert failed.overall_pass is False
    assert "benchmark:t3" in failed.failing_gates


def test_release_report_template_sections() -> None:
    result = run_release_gate(
        harness_condition_id="hcs:1",
        benchmark_results={"t3": {"passed": True}},
        calibration_required=False,
        operational_required=False,
        adversarial_required=False,
    )
    rendered = render_release_report(result)
    assert missing_report_sections(rendered) == []


def test_release_gate_cli_writes_report(tmp_path: Path) -> None:
    report = tmp_path / "release.json"
    result = CliRunner().invoke(
        app,
        [
            "release-gate",
            "--suite",
            "t3",
            "--no-calibration-required",
            "--no-adversarial-required",
            "--no-memory-gate-required",
            "--no-operational-gate-required",
            "--report-out",
            str(report),
        ],
    )
    assert result.exit_code == 0
    assert report.exists()
