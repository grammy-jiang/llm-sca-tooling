from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app
from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.release.ablation import (
    build_ablation_report,
    required_ablation_configs,
)
from llm_sca_tooling.release.adversarial import (
    default_adversarial_fixtures,
    run_adversarial_suite,
)
from llm_sca_tooling.release.calibration import (
    build_calibration_report,
    expected_calibration_error,
    macro_f1,
)
from llm_sca_tooling.release.models import (
    AblationConfig,
    AblationControlChange,
    BenchmarkSuiteResult,
    CalibrationSample,
    ReleaseImpact,
)
from llm_sca_tooling.release.operational_gates import (
    compute_operational_harness_gate,
)
from llm_sca_tooling.release.production_refresh import (
    build_refresh_record,
    convert_refresh_to_benchmark_instance,
)
from llm_sca_tooling.release.release_gate import ReleaseGateEvaluator
from llm_sca_tooling.release.report_templates import (
    missing_mandatory_sections,
    render_release_report,
)


def _sample(sample_id: str, probability: float, label: str) -> CalibrationSample:
    return CalibrationSample(
        sample_id=sample_id,
        family="fixture",
        predicted_probability=probability,
        predicted_label=label,
        gold_label=label,
    )


def test_calibration_report_gates_pass_and_fail() -> None:
    samples = [
        _sample("s1", 0.95, "safe"),
        _sample("s2", 0.95, "vulnerable"),
        _sample("s3", 0.95, "correct-but-overfit"),
    ]
    assert expected_calibration_error(samples) == pytest.approx(0.05)
    assert macro_f1(samples) == 1.0
    report = build_calibration_report(
        eval_run_id="eval:cal",
        model_backend="null",
        harness_condition_id="hcs:cal",
        patch_risk_samples=samples,
        impl_check_samples=[
            _sample("c1", 0.95, "satisfied"),
            _sample("c2", 0.95, "violated"),
        ],
        repo_qa_file_loc_accuracy=0.95,
        repo_qa_behaviour_tracing_accuracy=0.75,
        memory_her_eviction_delta_pp=3.0,
    )
    assert report.patch_risk_gate_passed is True
    assert report.impl_check_gate_passed is True
    failing = build_calibration_report(
        eval_run_id="eval:bad",
        model_backend="null",
        harness_condition_id="hcs:bad",
        patch_risk_samples=[
            CalibrationSample(
                sample_id="bad",
                family="fixture",
                predicted_probability=0.99,
                predicted_label="safe",
                gold_label="vulnerable",
            )
        ],
        impl_check_samples=[],
        repo_qa_file_loc_accuracy=0.50,
        repo_qa_behaviour_tracing_accuracy=0.20,
        memory_her_eviction_delta_pp=0.0,
    )
    assert failing.patch_risk_gate_passed is False
    assert failing.impl_check_gate_passed is False


def test_ablation_report_detects_unexpected_improvement() -> None:
    with pytest.raises(ValidationError):
        AblationConfig(
            ablation_id="bad",
            baseline_config_ref="baseline",
            modified_controls=[
                AblationControlChange(
                    control_name="a",
                    before_value="on",
                    after_value="off",
                ),
                AblationControlChange(
                    control_name="b",
                    before_value="on",
                    after_value="off",
                ),
            ],
            rationale="invalid",
        )
    configs = required_ablation_configs("baseline")
    report = build_ablation_report(
        baseline_eval_run_id="eval:base",
        baseline_metrics={
            "resolve_rate": 0.50,
            "policy_compliance_rate": 1.0,
            "trace_replay_success_rate": 1.0,
        },
        ablation_configs=[configs[1]],
        ablation_eval_run_ids=["eval:wide"],
        ablation_metrics={
            "eval:wide": {
                "resolve_rate": 0.60,
                "policy_compliance_rate": 0.80,
                "trace_replay_success_rate": 1.0,
            }
        },
    )
    assert report.release_impact == ReleaseImpact.unexpected_improvement
    assert report.per_ablation_delta[0].investigation_note


def test_operational_gate_runner_thresholds() -> None:
    passing_records = [
        {
            "trace_complete": True,
            "policy_compliant": True,
            "budget_reliable": True,
            "maintainability_oracle_passed": True,
            "manifest_regression_passed": True,
            "trace_replay_success": True,
            "accepted_verdict": True,
            "token_count": 10,
        }
        for _ in range(20)
    ]
    passing = compute_operational_harness_gate(
        eval_run_id="eval:op",
        run_records=passing_records,
        readiness_threshold_met=True,
    )
    assert passing.gate_passed is True
    failing = compute_operational_harness_gate(
        eval_run_id="eval:op",
        run_records=[
            *passing_records[:18],
            {
                "trace_complete": False,
                "policy_compliant": False,
                "budget_reliable": False,
                "maintainability_oracle_passed": False,
                "manifest_regression_passed": False,
                "trace_replay_success": False,
                "incidents": [{"severity": "P1", "status": "open"}],
            },
            {
                "trace_complete": False,
                "policy_compliant": False,
                "budget_reliable": False,
                "maintainability_oracle_passed": False,
                "manifest_regression_passed": False,
                "trace_replay_success": False,
            },
        ],
        readiness_threshold_met=False,
    )
    assert failing.gate_passed is False
    assert "manifest_regression" in failing.failing_gates
    assert "p0_p1_incident_closure" in failing.failing_gates


def test_adversarial_suite_and_production_refresh() -> None:
    results = run_adversarial_suite()
    # 6 v0.5.x fixtures + 4 v0.6.2 breadth additions (Plan 05).
    assert len(results) == 10
    assert all(result.passed for result in results)
    fixtures = default_adversarial_fixtures()
    fixtures[0]["expected_outcome"] = "ignored_instruction"
    assert run_adversarial_suite(fixtures)[0].passed is False
    record = build_refresh_record(
        source_run_id="run:prod",
        issue_text="failure in parser",
        repo_id="repo:1",
        fail_to_pass_tests_present=True,
        pass_to_pass_tests_present=True,
        test_relevance_validated=True,
        flaky_flag=False,
        approved=True,
        added_to_suite_id="suite:prod",
    )
    instance = convert_refresh_to_benchmark_instance(record)
    assert instance["gold_patch_ref"] == "hidden"
    assert instance["suite_id"] == "suite:prod"


# ── v0.6.2 adversarial-breadth regressions (Plan 05) ──────────────────────────
# One regression per new fixture so a single failure points at the specific
# attack shape, not the whole suite.


def _result_for(fixture_id: str):
    return next(r for r in run_adversarial_suite() if r.fixture_id == fixture_id)


def test_adversarial_indirect_prompt_injection_passes() -> None:
    """Indirect injection (attacker plants payload in a doc the agent reads)
    is distinct from direct prompt-injection.  Phase 18 §8.2."""
    result = _result_for("adv:indirect-prompt-injection")
    assert result.passed
    assert result.check_type == "prompt_injection"
    assert result.expected_outcome == result.actual_outcome == "typed_error"


def test_adversarial_scope_write_symlink_passes() -> None:
    """Symlink-traversal write — simple path-prefix scope checks miss it;
    the gate must catch it via the resolved-target check."""
    result = _result_for("adv:scope-write-symlink")
    assert result.passed
    assert result.check_type == "out_of_scope_write"
    assert result.expected_outcome == "process-noncompliant"


def test_adversarial_policy_bypass_test_mode_passes() -> None:
    """A common real-world bypass shape: offer the agent an escape hatch
    ("skip the check in test/dev mode").  The gate must refuse."""
    result = _result_for("adv:policy-bypass-test-mode")
    assert result.passed
    assert result.check_type == "multistep_policy_bypass"
    assert result.expected_outcome == "blocked"


def test_adversarial_reward_hack_test_only_fix_passes() -> None:
    """Reward-hacking variant: the proposed patch deletes / weakens the
    failing test instead of fixing the underlying defect."""
    result = _result_for("adv:reward-hack-test-only-fix")
    assert result.passed
    assert result.check_type == "reward_hackable_task"
    assert result.expected_outcome == "correct-but-overfit"


def test_release_gate_and_report_template() -> None:
    calibration = build_calibration_report(
        eval_run_id="eval:gate",
        model_backend="null",
        harness_condition_id="hcs:gate",
        patch_risk_samples=[_sample("p", 0.95, "safe")],
        impl_check_samples=[_sample("c", 0.95, "satisfied")],
        repo_qa_file_loc_accuracy=0.95,
        repo_qa_behaviour_tracing_accuracy=0.75,
        memory_her_eviction_delta_pp=3.0,
    )
    operational = compute_operational_harness_gate(
        eval_run_id="eval:gate",
        run_records=[
            {
                "trace_complete": True,
                "policy_compliant": True,
                "budget_reliable": True,
                "maintainability_oracle_passed": True,
                "manifest_regression_passed": True,
                "trace_replay_success": True,
            }
            for _ in range(10)
        ],
    )
    result = ReleaseGateEvaluator().evaluate(
        harness_condition_id="hcs:gate",
        benchmark_results=[
            BenchmarkSuiteResult(
                suite_id="t3",
                eval_run_id="eval:t3",
                status="completed",
                passed=True,
            )
        ],
        calibration_report=calibration,
        operational_gate_result=operational,
        adversarial_check_results=run_adversarial_suite(),
        memory_ship_gate_result_ref="memory:gate",
        ai_readiness_report_ref="readiness:gate",
    )
    assert result.overall_pass is True
    report = render_release_report(
        result=result,
        calibration=calibration,
        operational=operational,
    )
    assert missing_mandatory_sections(report) == []
    failed = ReleaseGateEvaluator().evaluate(
        harness_condition_id="hcs:gate",
        benchmark_results=[
            BenchmarkSuiteResult(
                suite_id="t3",
                eval_run_id="eval:t3",
                status="completed",
                passed=False,
            )
        ],
        fail_on_any=True,
    )
    assert failed.overall_pass is False
    assert "benchmarks" in failed.failing_gates


def test_release_gate_cli_writes_json(tmp_path: Path) -> None:
    runner = CliRunner()
    report = tmp_path / "release-gate.json"
    result = runner.invoke(
        app,
        [
            "release-gate",
            "--suite",
            "t3",
            "--report-out",
            str(report),
            "--fail-on-any",
        ],
    )
    assert result.exit_code == 0
    assert report.exists()
    assert "Overall pass" in result.output
    bad_suite = runner.invoke(app, ["release-gate", "--suite", "t5"])
    assert bad_suite.exit_code == 2


async def test_phase18_mcp_tools_and_prompts(tmp_path: Path) -> None:
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize(client_capabilities={"sampling": {"maxTokens": 1000}})
    repo = tmp_path / "repo"
    _write_minimal_repo(repo)
    try:
        tools = await server.list_tools()
        tool_names = {tool.name for tool in tools}
        assert {"run_operational_review", "run_readiness_audit"} <= tool_names
        op_prompt = await server.get_prompt("operational-review")
        assert "process-compliant" in op_prompt["instructions"]
        assert "Phase 18 full launcher" in op_prompt["limitation"]
        eval_result = await server.call_tool("run_eval_suite", {"suite": "t3"})
        assert eval_result.payload["eval_run"]["suite_id"] == "t3-cross-language"
        events = [
            {"type": "tool_call"},
            {"type": "gate_result"},
            {"type": "budget_event"},
            {"type": "final_verdict"},
            {"type": "verification_event"},
        ]
        op_result = await server.call_tool(
            "run_operational_review",
            {"run_id": "run:1", "run_events": events},
        )
        assert (
            op_result.payload["report"]["process_compliance_verdict"]
            == "process-compliant"
        )
        queued = await server.call_tool(
            "run_readiness_audit", {"repo": str(repo), "task": True}
        )
        task_id = queued.payload["task"]["task_id"]
        final = await _wait_task(server, task_id)
        assert final["status"] == "completed"
        assert final["result"]["report"]["repo"] == str(repo)
    finally:
        await server.close()


async def _wait_task(server: MCPServer, task_id: str) -> dict:
    for _ in range(100):
        status = await server.call_tool("task_status", {"task_id": task_id})
        task = status.payload["task"]
        if task["status"] in {"completed", "failed", "cancelled"}:
            return task
        await asyncio.sleep(0.01)
    raise AssertionError(f"task {task_id} did not finish")


def _write_minimal_repo(repo: Path) -> None:
    (repo / "docs").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "AGENTS.md").write_text("HC1\nHC2\n", encoding="utf-8")
    (repo / "Makefile").write_text("verify:\n\t@true\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "\n".join(["[project]", "name='fixture'", "ruff", "mypy", "bandit"]),
        encoding="utf-8",
    )
    (repo / "docs" / "llm-sca-tooling-implementation-plan.md").write_text(
        "plan",
        encoding="utf-8",
    )
