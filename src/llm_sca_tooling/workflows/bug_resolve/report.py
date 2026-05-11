"""Bug-resolve workflow orchestration."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.evaluation.models import now_ts
from llm_sca_tooling.patch_review.risk_classifier import classify_patch_risk
from llm_sca_tooling.workflows.bug_resolve.blast_radius_stub import compute_blast_radius
from llm_sca_tooling.workflows.bug_resolve.candidate_patch import NullPatchGenerator
from llm_sca_tooling.workflows.bug_resolve.certificate import build_certificate
from llm_sca_tooling.workflows.bug_resolve.config import default_workflow_config
from llm_sca_tooling.workflows.bug_resolve.gate_runner import run_gates
from llm_sca_tooling.workflows.bug_resolve.investigate import run_investigate
from llm_sca_tooling.workflows.bug_resolve.models import (
    BugResolveReport,
    GateRunnerResult,
    WorkflowConfig,
    WorkflowState,
)
from llm_sca_tooling.workflows.bug_resolve.monitor_hooks import (
    check_doom_loop,
    check_stale_snapshot,
)
from llm_sca_tooling.workflows.bug_resolve.patch_selection import select_patch
from llm_sca_tooling.workflows.bug_resolve.preconditions import draft_preconditions
from llm_sca_tooling.workflows.bug_resolve.repair_context import build_repair_context
from llm_sca_tooling.workflows.bug_resolve.reproduction_test import (
    generate_reproduction_test,
)
from llm_sca_tooling.workflows.bug_resolve.trace_manifest import write_trace_manifest


def run_issue_resolution(
    *,
    issue_text: str,
    run_id: str | None = None,
    config: WorkflowConfig | None = None,
    sandbox_root: Path | None = None,
    # test injection: simulate workflow states
    simulate_no_suspects: bool = False,
    simulate_budget_exhausted: bool = False,
    simulate_doom_loop: bool = False,
    gate_override: GateRunnerResult | None = None,
    newly_failing_tests: list[str] | None = None,
    new_critical_sarif: bool = False,
    simulate_trace_incomplete: bool = False,
) -> BugResolveReport:
    run_id = run_id or f"bug-resolve:{uuid.uuid4().hex[:8]}"
    config = config or default_workflow_config()
    start_ts = now_ts()

    state = WorkflowState(run_id=run_id)

    # ── STAGE: load ───────────────────────────────────────────────────────────
    state.stage = "load"
    state.stage_history.append("load")
    hcs = HarnessConditionSheet.create(run_id=run_id)

    if simulate_budget_exhausted:
        state.status = "budget_exhausted"
        state.monitor_events.append(
            {
                "monitor_type": "token_budget_hard_stop",
                "stage": "load",
                "loop_count": 0,
                "detail": "simulated budget exhaustion",
                "action_taken": "transition_budget_exhausted",
            }
        )
        return _assemble_report(
            run_id=run_id,
            state=state,
            hcs=hcs,
            issue_text_hash="simulated",
            investigate=None,
            patches=[],
            gate_results=[],
            selection=None,
            blast=None,
            pre_cond=None,
            post_cond=None,
            repro_test=None,
            cert=None,
            start_ts=start_ts,
            trace_incomplete=simulate_trace_incomplete,
        )

    # ── STAGE: investigate ────────────────────────────────────────────────────
    state.stage = "investigate"
    state.stage_history.append("investigate")
    investigate = run_investigate(
        run_id=run_id,
        issue_text=issue_text,
        simulate_no_suspects=simulate_no_suspects,
    )
    state.investigate_result = investigate.model_dump(mode="json")

    if not investigate.ranked_candidates:
        state.status = "completed_no_fix"
        return _assemble_report(
            run_id=run_id,
            state=state,
            hcs=hcs,
            issue_text_hash=investigate.issue_text_hash,
            investigate=investigate,
            patches=[],
            gate_results=[],
            selection=None,
            blast=None,
            pre_cond=None,
            post_cond=None,
            repro_test=None,
            cert=None,
            start_ts=start_ts,
            trace_incomplete=simulate_trace_incomplete,
        )

    # ── STAGE: repair ─────────────────────────────────────────────────────────
    state.stage = "repair"
    state.stage_history.append("repair")

    if simulate_doom_loop:
        state.loop_count = config.max_repair_loops
        doom = check_doom_loop(state, max_loops=config.max_repair_loops)
        if doom:
            state.status = "failed"
            return _assemble_report(
                run_id=run_id,
                state=state,
                hcs=hcs,
                issue_text_hash=investigate.issue_text_hash,
                investigate=investigate,
                patches=[],
                gate_results=[],
                selection=None,
                blast=None,
                pre_cond=None,
                post_cond=None,
                repro_test=None,
                cert=None,
                start_ts=start_ts,
                trace_incomplete=simulate_trace_incomplete,
            )

    ctx = build_repair_context(
        run_id=run_id,
        candidate_index=0,
        investigate=investigate,
        config=config,
    )
    patch = NullPatchGenerator().generate(ctx)
    state.repair_candidates.append(patch.model_dump(mode="json"))

    pre_cond = draft_preconditions(patch)
    post_cond = pre_cond

    # ── STAGE: dryrun ─────────────────────────────────────────────────────────
    state.stage = "dryrun"
    state.stage_history.append("dryrun")
    repro_test = generate_reproduction_test(patch)
    state.dryrun_predictions.append(
        {
            "candidate_index": 0,
            "method": "null",
            "repro_test_ref": f"repro:{run_id}/0",
        }
    )

    # ── STAGE: gates ──────────────────────────────────────────────────────────
    state.stage = "gates"
    state.stage_history.append("gates")
    cert = build_certificate(patch)

    if gate_override is not None:
        gate_result = gate_override
    else:
        gate_result = run_gates(
            patch,
            cert,
            new_critical_sarif=new_critical_sarif,
            newly_failing_tests=newly_failing_tests,
        )

    state.gate_results.append(gate_result.model_dump(mode="json"))

    # ── STAGE: patch_risk ─────────────────────────────────────────────────────
    state.stage = "patch_risk"
    state.stage_history.append("patch_risk")
    risk, _vector, _ctx_risk = classify_patch_risk(
        diff_text=patch.diff_text,
        after_failed=newly_failing_tests or [],
    )
    state.patch_risk_results.append(
        {"candidate_index": 0, "risk_class": risk.risk_class}
    )

    # ── STAGE: blast_radius ───────────────────────────────────────────────────
    state.stage = "blast_radius"
    state.stage_history.append("blast_radius")
    blast = compute_blast_radius(patch)
    state.blast_radius_result = blast.model_dump(mode="json")

    # ── STAGE: scope_audit ────────────────────────────────────────────────────
    state.stage = "scope_audit"
    state.stage_history.append("scope_audit")
    state.scope_audit_result = {
        "verdict": "unknown" if simulate_trace_incomplete else "in_scope",
        "out_of_scope_writes": [],
    }

    # ── STAGE: operational_review ─────────────────────────────────────────────
    state.stage = "operational_review"
    state.stage_history.append("operational_review")
    state.operational_verdict = "no_outstanding_incidents"

    # ── STAGE: trajectory ─────────────────────────────────────────────────────
    state.stage = "trajectory"
    state.stage_history.append("trajectory")

    # stale snapshot check
    check_stale_snapshot(
        state,
        snapshot_id=investigate.snapshot_id,
        current_snapshot_id=investigate.snapshot_id,
    )

    # patch selection
    patches = [patch]
    gate_results = [gate_result]
    selection = select_patch(
        run_id=run_id,
        patches=patches,
        gate_results=gate_results,
        investigate=investigate,
    )
    state.selected_patch = (
        patches[selection.selected_candidate_index].model_dump(mode="json")
        if selection.selected_candidate_index is not None
        else None
    )
    state.status = (
        "completed_success"
        if selection.selected_candidate_index is not None
        else "completed_no_fix"
    )

    return _assemble_report(
        run_id=run_id,
        state=state,
        hcs=hcs,
        issue_text_hash=investigate.issue_text_hash,
        investigate=investigate,
        patches=patches,
        gate_results=gate_results,
        selection=selection,
        blast=blast,
        pre_cond=pre_cond,
        post_cond=post_cond,
        repro_test=repro_test,
        cert=cert,
        start_ts=start_ts,
        trace_incomplete=simulate_trace_incomplete,
        risk_ref=f"patch-risk:{risk.diff_id}",
    )


def _assemble_report(
    *,
    run_id: str,
    state: WorkflowState,
    hcs: HarnessConditionSheet,
    issue_text_hash: str,
    investigate: Any,
    patches: list[Any],
    gate_results: list[Any],
    selection: Any,
    blast: Any,
    pre_cond: Any,
    post_cond: Any,
    repro_test: Any,
    cert: Any,
    start_ts: str,
    trace_incomplete: bool = False,
    risk_ref: str = "patch-risk:none",
) -> BugResolveReport:
    final_verdict = _compute_verdict(state, gate_results, selection)
    recommendation = _compute_recommendation(
        final_verdict, state, trace_incomplete=trace_incomplete
    )
    uncertainty = _build_uncertainty(state, investigate)

    _manifest = write_trace_manifest(
        state=state,
        issue_text_hash=issue_text_hash,
        harness_condition_id=hcs.hcs_id,
        start_ts=start_ts,
    )

    selected_ref = (
        f"patch:{run_id}/{selection.selected_candidate_index}"
        if selection and selection.selected_candidate_index is not None
        else None
    )

    return BugResolveReport(
        report_id=f"bug-resolve:{run_id}",
        run_id=run_id,
        harness_condition_id=hcs.hcs_id,
        issue_text_hash=issue_text_hash,
        investigate_result_ref=f"investigate:{run_id}",
        selected_patch_ref=selected_ref,
        candidate_patches_ref=f"patches:{run_id}",
        precondition_draft_ref=f"precond:{run_id}/0",
        postcondition_draft_ref=f"postcond:{run_id}/0",
        reproduction_tests_ref=f"repro:{run_id}",
        certificate_ref=f"cert:{run_id}/0",
        gate_results_ref=f"gates:{run_id}",
        patch_risk_result_ref=risk_ref,
        blast_radius_result_ref=f"blast:{run_id}/0",
        scope_audit_result_ref=f"scope:{run_id}",
        dryrun_prediction_ref=f"dryrun:{run_id}",
        dryrun_mismatches_ref=f"dryrun-mismatches:{run_id}",
        operational_verdict=state.operational_verdict,
        final_verdict=final_verdict,
        recommendation=recommendation,
        uncertainty=uncertainty,
        session_trace_manifest_ref=f"trace:{run_id}",
    )


def _compute_verdict(
    state: WorkflowState, gate_results: list[Any], selection: Any
) -> str:
    if state.status == "budget_exhausted":
        return "budget_exhausted"
    if state.status == "failed":
        return "uncertain"
    if state.status == "completed_no_fix":
        return "no_fix_found"
    if not gate_results:
        return "no_fix_found"
    has_block = any(
        (
            not g.overall_gate_pass
            if hasattr(g, "overall_gate_pass")
            else not g.get("overall_gate_pass", True)
        )
        for g in gate_results
    )
    if has_block:
        return "no_fix_found"
    if selection and selection.selected_candidate_index is not None:
        return "resolved_with_risk"
    return "no_fix_found"


def _compute_recommendation(
    verdict: str, state: WorkflowState, *, trace_incomplete: bool
) -> str:
    if trace_incomplete:
        return "block"
    if state.status == "budget_exhausted":
        return "block"
    if state.status == "failed":
        return "block"
    if verdict == "resolved":
        return "merge-supporting"
    if verdict == "resolved_with_risk":
        return "review-required"
    if verdict in {"no_fix_found", "uncertain"}:
        return "block"
    if verdict == "budget_exhausted":
        return "block"
    return "unknown"


def _build_uncertainty(state: WorkflowState, investigate: Any) -> str:
    parts: list[str] = []
    if investigate and getattr(investigate, "stale_snapshot_flag", False):
        parts.append("stale_snapshot")
    if state.monitor_events:
        types = {m.get("monitor_type", "unknown") for m in state.monitor_events}
        parts.append(f"monitor_events:{','.join(sorted(types))}")
    if state.status == "budget_exhausted":
        parts.append("budget_exhausted")
    return ";".join(parts)
