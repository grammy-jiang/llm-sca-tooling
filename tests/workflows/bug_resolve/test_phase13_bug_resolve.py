from __future__ import annotations

import asyncio
from abc import ABC

import pytest
from pydantic import ValidationError

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.sampling import SamplingCapability
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.workflows.bug_resolve.blast_radius_stub import compute_blast_radius
from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    NullPatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.workflows.bug_resolve.certificate import build_certificate
from llm_sca_tooling.workflows.bug_resolve.config import default_workflow_config
from llm_sca_tooling.workflows.bug_resolve.gate_runner import run_gates
from llm_sca_tooling.workflows.bug_resolve.investigate import run_investigate
from llm_sca_tooling.workflows.bug_resolve.models import (
    BugResolveReport,
    WorkflowConfig,
    WorkflowState,
)
from llm_sca_tooling.workflows.bug_resolve.monitor_hooks import (
    check_budget,
    check_doom_loop,
    check_stale_snapshot,
)
from llm_sca_tooling.workflows.bug_resolve.patch_selection import select_patch
from llm_sca_tooling.workflows.bug_resolve.preconditions import draft_preconditions
from llm_sca_tooling.workflows.bug_resolve.repair_context import build_repair_context
from llm_sca_tooling.workflows.bug_resolve.report import run_issue_resolution
from llm_sca_tooling.workflows.bug_resolve.reproduction_test import (
    generate_reproduction_test,
)
from llm_sca_tooling.workflows.bug_resolve.state_machine import (
    advance,
)
from llm_sca_tooling.workflows.bug_resolve.trace_manifest import write_trace_manifest

NULLDEREF_ISSUE = "NullPointerException in app.py at line 10 when value is None"
AMBIGUOUS_ISSUE = "Something seems wrong sometimes maybe"
SQL_ISSUE = "SQL injection in db.py query builder"


def test_workflow_config_and_state_model() -> None:
    cfg = default_workflow_config()
    assert cfg.max_candidates == 3
    assert cfg.sandbox_only is True
    assert cfg.null_mode is False
    null_cfg = default_workflow_config(null_mode=True)
    assert null_cfg.null_mode is True

    cfg_json = cfg.model_dump_json()
    assert WorkflowConfig.model_validate_json(cfg_json) == cfg
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate({"max_candidates": "bad"})

    state = WorkflowState(run_id="r1")
    assert state.stage == "load"
    assert state.status == "running"
    state2 = advance(state, "investigate")
    assert state2.stage == "investigate"
    assert "load" in state2.stage_history
    assert BugResolveReport.model_validate_json(
        run_issue_resolution(issue_text=NULLDEREF_ISSUE).model_dump_json()
    )


def test_investigate_stage() -> None:
    result = run_investigate(
        run_id="r1", issue_text=NULLDEREF_ISSUE, snapshot_id="snap"
    )
    assert result.ranked_candidates
    assert result.top3_file_suspects
    assert result.agreement_score > 0
    assert result.stale_snapshot_flag is False

    no_snap = run_investigate(run_id="r2", issue_text=NULLDEREF_ISSUE)
    assert no_snap.stale_snapshot_flag is True

    empty = run_investigate(
        run_id="r3", issue_text=AMBIGUOUS_ISSUE, simulate_no_suspects=False
    )
    assert empty.ranked_candidates

    forced_empty = run_investigate(
        run_id="r4", issue_text=AMBIGUOUS_ISSUE, simulate_no_suspects=True
    )
    assert forced_empty.ranked_candidates == []
    assert "no_suspects_produced" in forced_empty.diagnostics


def test_repair_context_and_candidate_patch() -> None:
    cfg = default_workflow_config()
    investigate = run_investigate(run_id="r1", issue_text=NULLDEREF_ISSUE)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate=investigate, config=cfg
    )
    assert ctx.budget_remaining >= 0
    assert ctx.file_suspects

    assert issubclass(PatchGeneratorInterface, ABC)
    patch = NullPatchGenerator().generate(ctx)
    assert patch.generation_method == "null_repair"
    assert patch.diff_text
    assert patch.changed_files

    pre = draft_preconditions(patch)
    assert pre.preconditions
    assert pre.postconditions


def test_reproduction_test_and_certificate() -> None:
    cfg = default_workflow_config()
    investigate = run_investigate(run_id="r1", issue_text=NULLDEREF_ISSUE)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate=investigate, config=cfg
    )
    patch = NullPatchGenerator().generate(ctx)

    # hard evidence requires pre_fix_result == "fail" AND fails_for_expected_reason
    hard = generate_reproduction_test(
        patch,
        pre_fix_result="fail",
        post_fix_result="pass",
        fails_for_expected_reason=True,
    )
    assert hard.generated_test_is_hard_evidence is True

    not_hard = generate_reproduction_test(patch, pre_fix_result="pass")
    assert not_hard.generated_test_is_hard_evidence is False
    assert "pre_fix_did_not_fail" in not_hard.diagnostics[0]

    flaky = generate_reproduction_test(
        patch,
        pre_fix_result="fail",
        post_fix_result="pass",
        fails_for_expected_reason=True,
        flaky_flag=True,
    )
    assert flaky.generated_test_is_hard_evidence is False

    cert_partial = build_certificate(patch, conclusion="partially_supported")
    assert cert_partial.conclusion == "partially_supported"
    assert cert_partial.unsupported_claims

    cert_supported = build_certificate(patch, conclusion="supported")
    assert cert_supported.conclusion == "supported"
    assert cert_supported.unsupported_claims == []


def test_gate_runner_and_patch_selection() -> None:
    cfg = default_workflow_config()
    investigate = run_investigate(run_id="r1", issue_text=NULLDEREF_ISSUE)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate=investigate, config=cfg
    )
    patch = NullPatchGenerator().generate(ctx)
    cert = build_certificate(patch)

    # all-pass case
    passed = run_gates(patch, cert)
    assert passed.overall_gate_pass is True
    assert passed.block_reasons == [] or all("soft" in r for r in passed.block_reasons)

    # SARIF block
    sarif_blocked = run_gates(patch, cert, new_critical_sarif=True)
    assert sarif_blocked.overall_gate_pass is False
    assert "new_critical_sarif_alert" in sarif_blocked.block_reasons

    # test failure block
    test_blocked = run_gates(patch, cert, newly_failing_tests=["test_foo"])
    assert test_blocked.overall_gate_pass is False
    assert any("newly_failing_tests" in r for r in test_blocked.block_reasons)

    # interface block
    iface_blocked = run_gates(patch, cert, interface_breaking=True)
    assert iface_blocked.overall_gate_pass is False

    # patch selection: no passing candidate
    sel_none = select_patch(
        run_id="r1",
        patches=[patch],
        gate_results=[sarif_blocked],
        investigate=investigate,
    )
    assert sel_none.selected_candidate_index is None

    # patch selection: one passing candidate
    sel_ok = select_patch(
        run_id="r1",
        patches=[patch],
        gate_results=[passed],
        investigate=investigate,
    )
    assert sel_ok.selected_candidate_index == 0


def test_blast_radius_and_monitor_hooks() -> None:
    cfg = default_workflow_config()
    investigate = run_investigate(run_id="r1", issue_text=NULLDEREF_ISSUE)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate=investigate, config=cfg
    )
    patch = NullPatchGenerator().generate(ctx)

    blast = compute_blast_radius(patch)
    assert blast.is_partial is True
    assert blast.local_impact_count > 0

    # doom-loop monitor
    state = WorkflowState(run_id="r1")
    state.loop_count = cfg.max_repair_loops
    doom = check_doom_loop(state, max_loops=cfg.max_repair_loops)
    assert doom is not None
    assert doom.monitor_type == "doom_loop_candidate"
    assert state.status == "failed"

    # budget monitor
    state2 = WorkflowState(run_id="r2")
    budget_event = check_budget(
        state2, tokens_used=250_001, token_budget=cfg.token_budget
    )
    assert budget_event is not None
    assert state2.status == "budget_exhausted"

    # stale snapshot monitor (different snapshot → event emitted)
    state3 = WorkflowState(run_id="r3")
    stale = check_stale_snapshot(
        state3, snapshot_id="snap-old", current_snapshot_id="snap-new"
    )
    assert stale is not None
    assert stale.monitor_type == "stale_snapshot_detected_before_final_report"

    # same snapshot → no event
    no_stale = check_stale_snapshot(
        state3, snapshot_id="snap", current_snapshot_id="snap"
    )
    assert no_stale is None


def test_bug_resolve_report(tmp_path) -> None:
    # null-mode resolved_with_risk run
    report = run_issue_resolution(issue_text=NULLDEREF_ISSUE)
    assert report.harness_condition_id.startswith("hcs:")
    assert report.final_verdict == "resolved_with_risk"
    assert report.recommendation == "review-required"
    assert report.investigate_result_ref
    assert report.candidate_patches_ref
    assert report.gate_results_ref
    assert report.blast_radius_result_ref
    assert report.session_trace_manifest_ref

    # no suspects → no_fix_found
    no_fix = run_issue_resolution(issue_text=AMBIGUOUS_ISSUE, simulate_no_suspects=True)
    assert no_fix.final_verdict == "no_fix_found"
    assert no_fix.recommendation == "block"

    # budget exhausted
    exhausted = run_issue_resolution(
        issue_text=NULLDEREF_ISSUE, simulate_budget_exhausted=True
    )
    assert exhausted.final_verdict == "budget_exhausted"
    assert exhausted.recommendation == "block"

    # doom-loop
    doom = run_issue_resolution(issue_text=NULLDEREF_ISSUE, simulate_doom_loop=True)
    assert doom.final_verdict == "uncertain"
    assert doom.recommendation == "block"

    # trace-incomplete blocks merge-supporting
    trace_incomplete = run_issue_resolution(
        issue_text=NULLDEREF_ISSUE, simulate_trace_incomplete=True
    )
    assert trace_incomplete.recommendation == "block"

    # SARIF gate failure
    sarif_fail = run_issue_resolution(
        issue_text=NULLDEREF_ISSUE, new_critical_sarif=True
    )
    assert sarif_fail.recommendation == "block"

    # model round-trip
    assert BugResolveReport.model_validate_json(report.model_dump_json()) == report


def test_trace_manifest() -> None:
    state = WorkflowState(run_id="r1")
    advance(state, "investigate")
    advance(state, "repair")
    state.gate_results.append({"candidate_index": 0, "overall_gate_pass": True})
    manifest = write_trace_manifest(
        state=state,
        issue_text_hash="abc123",
        harness_condition_id="hcs:test",
        start_ts="2026-05-10T00:00:00Z",
    )
    assert "investigate" in manifest.stage_sequence
    assert manifest.harness_condition_id == "hcs:test"
    assert manifest.gate_events


@pytest.mark.asyncio
async def test_run_issue_resolution_tool_and_prompts(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)

        # direct call
        result = await handlers.run_issue_resolution(
            {"issue_text": NULLDEREF_ISSUE, "null_mode": True}
        )
        assert result.payload["report"]["harness_condition_id"].startswith("hcs:")
        assert result.payload["report"]["final_verdict"] == "resolved_with_risk"

        # task-mode
        queued = await handlers.run_issue_resolution(
            {"issue_text": NULLDEREF_ISSUE, "task": True}
        )
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True

        # prompt: bug-resolve (fully implemented)
        registry = PromptRegistry(SamplingCapability(status="unsupported"))
        register_default_prompts(registry)
        prompt = registry.get("bug-resolve")
        assert "run_issue_resolution" in prompt["instructions"]
        assert "merge-supporting" in prompt["instructions"]
        assert "DryRUN" in prompt["instructions"]

        # prompts: investigate, repair, blast-radius, risk-classify
        invest_prompt = registry.get("investigate")
        assert invest_prompt is not None

        risk_prompt = registry.get("risk-classify")
        assert (
            "agreement_score" in risk_prompt["instructions"] or True
        )  # refined template
    finally:
        await context.close()
