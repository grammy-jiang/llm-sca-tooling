"""End-to-end state machine tests for the bug-resolve workflow."""

from __future__ import annotations

from typing import Any

import pytest

from llm_sca_tooling.workflows.bug_resolve import (
    BugResolveWorkflow,
    WorkflowConfig,
    run_bug_resolve_workflow,
)
from llm_sca_tooling.workflows.bug_resolve.models import (
    FinalVerdict,
    RecommendationValue,
    StatusValue,
)


async def test_null_mode_resolved() -> None:
    cfg = WorkflowConfig(null_mode=True)
    report, state, trace = await run_bug_resolve_workflow(
        run_id="r1", issue_text="NPE in foo", config=cfg
    )
    assert report.final_verdict is FinalVerdict.RESOLVED
    assert report.recommendation is RecommendationValue.MERGE_SUPPORTING
    assert state.status is StatusValue.COMPLETED_SUCCESS
    assert "trajectory" in [s.value for s in trace.stage_sequence]


async def test_empty_issue_no_fix() -> None:
    cfg = WorkflowConfig(null_mode=True)
    report, state, _ = await run_bug_resolve_workflow(
        run_id="r1", issue_text="", config=cfg
    )
    assert report.final_verdict is FinalVerdict.NO_FIX_FOUND
    assert state.status is StatusValue.COMPLETED_NO_FIX


async def test_budget_exhausted() -> None:
    cfg = WorkflowConfig(null_mode=True, context_budget=1)
    report, state, _ = await run_bug_resolve_workflow(
        run_id="r1", issue_text="NPE", config=cfg
    )
    assert report.final_verdict is FinalVerdict.BUDGET_EXHAUSTED
    assert state.status is StatusValue.BUDGET_EXHAUSTED
    assert report.recommendation is RecommendationValue.BLOCK


async def test_gate_failure_no_fix() -> None:
    async def fail_gate(_: dict[str, Any]) -> dict[str, Any]:
        return {"pass": False}

    async def pass_gate(_: dict[str, Any]) -> dict[str, Any]:
        return {"pass": True}

    cfg = WorkflowConfig(null_mode=True, max_candidates=2)
    report, state, _ = await run_bug_resolve_workflow(
        run_id="r1",
        issue_text="NPE in foo",
        config=cfg,
        sarif_gate=fail_gate,
        build_gate=pass_gate,
        test_gate=pass_gate,
        interface_gate=pass_gate,
    )
    assert report.final_verdict is FinalVerdict.NO_FIX_FOUND
    assert report.recommendation is RecommendationValue.BLOCK


async def test_harness_condition_in_report() -> None:
    cfg = WorkflowConfig(null_mode=True)
    report, _, _ = await run_bug_resolve_workflow(
        run_id="r1",
        issue_text="NPE",
        config=cfg,
        harness_condition_id="hcs:custom",
    )
    assert report.harness_condition_id == "hcs:custom"


async def test_run_bug_resolve_workflow_returns_three_tuple() -> None:
    cfg = WorkflowConfig(null_mode=True)
    out = await run_bug_resolve_workflow(run_id="r1", issue_text="NPE", config=cfg)
    assert len(out) == 3


async def test_doom_loop_fires_when_repair_loops_exhaust() -> None:
    # max_repair_loops=1 with all gates failing; loop_count grows on success only,
    # so this test inspects gate-fail repeated path. Use small max_candidates and
    # confirm the workflow exits cleanly.
    async def fail_gate(_: dict[str, Any]) -> dict[str, Any]:
        return {"pass": False}

    async def pass_gate(_: dict[str, Any]) -> dict[str, Any]:
        return {"pass": True}

    cfg = WorkflowConfig(null_mode=True, max_candidates=10, max_repair_loops=1)
    report, _, _ = await run_bug_resolve_workflow(
        run_id="r1",
        issue_text="NPE in foo",
        config=cfg,
        sarif_gate=fail_gate,
        build_gate=pass_gate,
        test_gate=pass_gate,
        interface_gate=pass_gate,
    )
    assert report.recommendation is RecommendationValue.BLOCK


async def test_workflow_class_run_directly() -> None:
    wf = BugResolveWorkflow(
        run_id="r1",
        issue_text="NPE",
        config=WorkflowConfig(null_mode=True),
    )
    report, state, trace = await wf.run()
    assert report.run_id == "r1"
    assert state.run_id == "r1"
    assert trace.run_id == "r1"


async def test_trace_records_stages() -> None:
    cfg = WorkflowConfig(null_mode=True)
    _, _, trace = await run_bug_resolve_workflow(
        run_id="r1", issue_text="NPE", config=cfg
    )
    stages = {s.value for s in trace.stage_sequence}
    for required in (
        "load",
        "investigate",
        "repair",
        "dryrun",
        "gates",
        "patch_risk",
        "blast_radius",
        "scope_audit",
        "operational_review",
        "trajectory",
    ):
        assert required in stages, required


@pytest.mark.parametrize("null_mode", [True])
async def test_null_mode_produces_repair_candidate(null_mode: bool) -> None:
    cfg = WorkflowConfig(null_mode=null_mode)
    _, state, _ = await run_bug_resolve_workflow(
        run_id="r1", issue_text="NPE", config=cfg
    )
    assert state.repair_candidates
    assert state.selected_patch is not None
