from __future__ import annotations

from llm_sca_tooling.harness.condition import HarnessConditionWriter


def test_harness_condition_writer_returns_required_sections(tmp_path) -> None:
    sheet = HarnessConditionWriter(tmp_path).capture(
        run_id="run:1",
        phase="Phase H0",
        runtime_version="0.1.0",
        model_backend="none",
        toolset_hash="hash",
        permission_profile="scoped-edit",
        context_budget=1000,
        gates_enabled=["pytest"],
        gates_disabled=[],
        trace_location=".agent/traces/session.jsonl",
        trace_completeness="complete",
        redaction_policy="redacted",
    )
    assert sheet["runtime_and_model"]["model_backend"] == "none"
    assert (tmp_path / "run_1.harness-condition.json").exists()
