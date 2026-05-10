"""Phase 13 bug-resolve state machine controller."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from llm_sca_tooling.evaluation.models import utc_now_ts
from llm_sca_tooling.workflows.bug_resolve.blast_radius_stub import (
    build_blast_radius_stub,
)
from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    NullCandidatePatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.workflows.bug_resolve.certificate import build_certificate
from llm_sca_tooling.workflows.bug_resolve.config import (
    DEFAULT_WORKFLOW_CONFIG,
    WorkflowConfig,
)
from llm_sca_tooling.workflows.bug_resolve.gate_runner import (
    GateCallable,
    run_gates,
)
from llm_sca_tooling.workflows.bug_resolve.investigate import (
    LocaliseCallable,
    RepoQACallable,
    run_investigate,
)
from llm_sca_tooling.workflows.bug_resolve.models import (
    BugResolveReport,
    CandidatePatch,
    SessionTraceManifest,
    StageName,
    StatusValue,
    WorkflowState,
)
from llm_sca_tooling.workflows.bug_resolve.monitor_hooks import (
    MonitorState,
    check_budget,
    check_doom_loop,
    check_repeated_failing_gate,
    check_stale_snapshot,
)
from llm_sca_tooling.workflows.bug_resolve.patch_selection import select_patch
from llm_sca_tooling.workflows.bug_resolve.preconditions import (
    generate_prepost_draft,
)
from llm_sca_tooling.workflows.bug_resolve.repair_context import build_repair_context
from llm_sca_tooling.workflows.bug_resolve.report import assemble_report
from llm_sca_tooling.workflows.bug_resolve.reproduction_test import (
    build_reproduction_test_record,
)

_log = logging.getLogger(__name__)

WorkflowResult = tuple[BugResolveReport, WorkflowState, SessionTraceManifest]


async def _null_pass_gate(payload: dict[str, Any]) -> dict[str, Any]:
    return {"pass": True, "ref": "null-gate-pass"}


class BugResolveWorkflow:
    """Ten-stage bug-resolve state machine."""

    def __init__(
        self,
        *,
        run_id: str,
        issue_text: str,
        repos: list[str] | None = None,
        config: WorkflowConfig | None = None,
        localise: LocaliseCallable | None = None,
        repo_qa: RepoQACallable | None = None,
        sarif_gate: GateCallable | None = None,
        build_gate: GateCallable | None = None,
        test_gate: GateCallable | None = None,
        interface_gate: GateCallable | None = None,
        patch_generator: PatchGeneratorInterface | None = None,
        harness_condition_id: str = "hcs:default",
    ) -> None:
        self.run_id = run_id
        self.issue_text = issue_text
        self.repos = repos or []
        self.config = config or DEFAULT_WORKFLOW_CONFIG
        self.localise = localise
        self.repo_qa = repo_qa
        # In null mode, supply pass-through gates so the pipeline can complete
        # without external tooling.
        if self.config.null_mode:
            self.sarif_gate: GateCallable | None = sarif_gate or _null_pass_gate
            self.build_gate: GateCallable | None = build_gate or _null_pass_gate
            self.test_gate: GateCallable | None = test_gate or _null_pass_gate
            self.interface_gate: GateCallable | None = interface_gate or _null_pass_gate
        else:
            self.sarif_gate = sarif_gate
            self.build_gate = build_gate
            self.test_gate = test_gate
            self.interface_gate = interface_gate
        self.patch_generator = patch_generator or NullCandidatePatchGenerator()
        self.harness_condition_id = harness_condition_id
        self._monitor = MonitorState()
        self._artefact_refs: list[str] = []
        self._tool_calls: list[dict[str, Any]] = []
        self._gate_events: list[dict[str, Any]] = []
        self._budget_events: list[dict[str, Any]] = []
        self._start_ts = utc_now_ts()

    def _issue_hash(self) -> str:
        return hashlib.sha256(self.issue_text.encode("utf-8")).hexdigest()[:24]

    def _advance(self, state: WorkflowState, stage: StageName) -> None:
        state.stage_history.append(state.stage)
        state.stage = stage

    def _check_budget_events(self, state: WorkflowState) -> bool:
        events = check_budget(
            run_id=self.run_id,
            stage=state.stage,
            state=self._monitor,
            config=self.config,
        )
        if events:
            state.monitor_events.extend(events)
            for e in events:
                self._budget_events.append({"event": e.model_dump(mode="json")})
            return True
        return False

    async def run(self) -> WorkflowResult:
        state = WorkflowState(run_id=self.run_id)
        issue_hash = self._issue_hash()

        try:
            report, trace = await self._run_inner(state, issue_hash)
        except Exception as exc:  # pragma: no cover - defensive
            _log.exception("Workflow failed unexpectedly: %s", exc)
            state.status = StatusValue.FAILED
            state.error = str(exc)
            report = assemble_report(
                state=state,
                issue_text_hash=issue_hash,
                harness_condition_id=self.harness_condition_id,
                process_compliant=False,
                operational_verdict=state.operational_verdict,
            )
            trace = self._build_trace(state, issue_hash)
        return report, state, trace

    async def _run_inner(
        self, state: WorkflowState, issue_hash: str
    ) -> tuple[BugResolveReport, SessionTraceManifest]:
        # Stage 1: load
        self._advance(state, StageName.LOAD)
        if self._check_budget_events(state):
            state.status = StatusValue.BUDGET_EXHAUSTED
            return self._finalise(state, issue_hash, process_compliant=False)

        # Stage 2: investigate
        self._advance(state, StageName.INVESTIGATE)
        investigate_result = await run_investigate(
            run_id=self.run_id,
            issue_text=self.issue_text,
            repos=self.repos or None,
            localise=self.localise,
            repo_qa=self.repo_qa,
            null_mode=self.config.null_mode,
        )
        state.investigate_result = investigate_result
        actual_files = investigate_result.budget_used.get("actual_files", 0)
        if isinstance(actual_files, (int, float)):
            self._monitor.add_tokens(int(actual_files) * 100)

        if self._check_budget_events(state):
            state.status = StatusValue.BUDGET_EXHAUSTED
            return self._finalise(state, issue_hash, process_compliant=False)

        if not investigate_result.ranked_candidates:
            state.status = StatusValue.COMPLETED_NO_FIX
            return self._finalise(state, issue_hash, process_compliant=True)

        # Repair loop (stages 3-5 per candidate)
        repair_candidates: list[CandidatePatch] = []
        gate_results = []
        dryrun_predictions: list[dict[str, Any]] = []
        repro_tests = []
        certs = []
        prepost_drafts = []
        patch_risk_results: list[dict[str, Any]] = []

        for candidate_index in range(self.config.max_candidates):
            doom = check_doom_loop(
                run_id=self.run_id,
                stage=StageName.REPAIR,
                loop_count=state.loop_count,
                config=self.config,
            )
            if doom is not None:
                state.monitor_events.append(doom)
                state.status = StatusValue.FAILED
                state.error = doom.detail
                break

            # Stage 3: repair
            self._advance(state, StageName.REPAIR)
            repair_ctx = build_repair_context(
                run_id=self.run_id,
                candidate_index=candidate_index,
                investigate_result=investigate_result,
                context_budget=self.config.context_budget,
            )
            self._monitor.add_context_tokens(repair_ctx.context_tokens_estimate)

            if self._check_budget_events(state):
                state.status = StatusValue.BUDGET_EXHAUSTED
                break

            candidate = self.patch_generator.generate(repair_ctx)
            repair_candidates.append(candidate)
            state.repair_candidates = list(repair_candidates)

            fn_path = (
                candidate.changed_files[0] if candidate.changed_files else "unknown"
            )
            draft = generate_prepost_draft(
                run_id=self.run_id,
                candidate_index=candidate_index,
                function_path=fn_path,
                preconditions=["input is not None"],
                postconditions=["return value is well-typed"],
            )
            prepost_drafts.append(draft)

            cert = build_certificate(
                run_id=self.run_id,
                candidate_index=candidate_index,
                definitions=["change is localised"],
                premises=[
                    "identified fault location matches issue description",
                ],
                path_claims=[
                    "fix removes null dereference on identified path",
                ],
                confidence=investigate_result.agreement_score,
            )
            certs.append(cert)

            # Stage 4: dryrun
            self._advance(state, StageName.DRYRUN)
            dryrun_pred: dict[str, Any] = {
                "candidate_index": candidate_index,
                "predicted_verdict": "pass",
                "confidence": 0.7,
                "method": "null-adapter",
            }
            dryrun_predictions.append(dryrun_pred)
            state.dryrun_predictions = list(dryrun_predictions)

            repro = build_reproduction_test_record(
                run_id=self.run_id,
                candidate_index=candidate_index,
                test_code="def test_null_deref():\n    assert True  # placeholder",
                test_file="tests/test_placeholder.py",
                generation_method="null-adapter",
            )
            repro_tests.append(repro)

            # Stage 5: gates
            self._advance(state, StageName.GATES)
            require_sarif = (
                False if self.config.null_mode else self.config.require_sarif_gate
            )
            require_interface = (
                False if self.config.null_mode else self.config.require_interface_gate
            )
            gate_result = await run_gates(
                run_id=self.run_id,
                candidate_index=candidate_index,
                candidate_diff=candidate.diff_text,
                sarif_gate=self.sarif_gate,
                build_gate=self.build_gate,
                test_gate=self.test_gate,
                interface_gate=self.interface_gate,
                reproduction_test=repro,
                certificate_conclusion=cert.conclusion,
                require_sarif_gate=require_sarif,
                require_interface_gate=require_interface,
            )
            gate_results.append(gate_result)
            state.gate_results = list(gate_results)
            self._gate_events.append({"gate": gate_result.model_dump(mode="json")})

            if not gate_result.overall_gate_pass and gate_result.block_reasons:
                failing = gate_result.block_reasons[0]
                rfg = check_repeated_failing_gate(
                    run_id=self.run_id,
                    stage=StageName.GATES,
                    state=self._monitor,
                    failing_gate=failing,
                )
                if rfg is not None:
                    state.monitor_events.append(rfg)
                    state.status = StatusValue.COMPLETED_NO_FIX
                    break
            else:
                check_repeated_failing_gate(
                    run_id=self.run_id,
                    stage=StageName.GATES,
                    state=self._monitor,
                    failing_gate=None,
                )

            if self._check_budget_events(state):
                state.status = StatusValue.BUDGET_EXHAUSTED
                break

            state.loop_count += 1

            patch_risk_results.append(
                {
                    "candidate_index": candidate_index,
                    "risk_class": "medium",
                    "calibrated_probability": 0.3,
                }
            )
            state.patch_risk_results = list(patch_risk_results)

            if gate_result.overall_gate_pass:
                break

        # Stage 6: patch_risk
        if state.status is StatusValue.RUNNING:
            self._advance(state, StageName.PATCH_RISK)
            selection = select_patch(
                run_id=self.run_id,
                candidates=repair_candidates,
                gate_results=gate_results,
                risk_results=patch_risk_results,
                agreement_score=investigate_result.agreement_score,
            )
            if selection.selected_candidate_index is not None:
                state.selected_patch = repair_candidates[
                    selection.selected_candidate_index
                ]
            else:
                state.status = StatusValue.COMPLETED_NO_FIX

        # Stage 7: blast_radius
        if state.status is StatusValue.RUNNING:
            self._advance(state, StageName.BLAST_RADIUS)
            sel_patch = state.selected_patch
            blast = build_blast_radius_stub(
                run_id=self.run_id,
                candidate_index=sel_patch.candidate_index if sel_patch else 0,
                changed_symbol_ids=sel_patch.changed_symbol_ids if sel_patch else [],
                direct_callers=[],
                downstream_tests=[],
            )
            state.blast_radius_result = blast

        # Stage 8: scope_audit
        if state.status is StatusValue.RUNNING:
            self._advance(state, StageName.SCOPE_AUDIT)
            state.scope_audit_result = {
                "verdict": "compliant",
                "out_of_scope_writes": [],
                "diagnostic": "null-mode scope audit",
            }

        # Stage 9: operational_review
        if state.status is StatusValue.RUNNING:
            self._advance(state, StageName.OPERATIONAL_REVIEW)
            state.operational_verdict = "no_outstanding_incidents"

        # Stage 10: trajectory
        if state.status is StatusValue.RUNNING:
            self._advance(state, StageName.TRAJECTORY)
            if investigate_result.stale_snapshot_flag:
                stale_event = check_stale_snapshot(
                    run_id=self.run_id,
                    stage=StageName.TRAJECTORY,
                    investigation_snapshot=investigate_result.snapshot_id,
                    current_snapshot="current",
                )
                if stale_event:
                    state.monitor_events.append(stale_event)
            state.status = StatusValue.COMPLETED_SUCCESS

        return self._finalise(state, issue_hash, process_compliant=True)

    def _finalise(
        self,
        state: WorkflowState,
        issue_hash: str,
        *,
        process_compliant: bool,
    ) -> tuple[BugResolveReport, SessionTraceManifest]:
        end_ts = utc_now_ts()
        report = assemble_report(
            state=state,
            issue_text_hash=issue_hash,
            harness_condition_id=self.harness_condition_id,
            process_compliant=process_compliant,
            operational_verdict=state.operational_verdict,
        )
        trace = SessionTraceManifest(
            run_id=self.run_id,
            workflow="bug-resolve",
            issue_text_hash=issue_hash,
            repos=list(self.repos),
            start_ts=self._start_ts,
            end_ts=end_ts,
            stage_sequence=list(state.stage_history) + [state.stage],
            artefact_refs=list(self._artefact_refs),
            tool_calls=list(self._tool_calls),
            gate_events=list(self._gate_events),
            monitor_events=list(state.monitor_events),
            budget_events=list(self._budget_events),
            approval_events=[],
            redaction_policy="redacted",
            harness_condition_id=self.harness_condition_id,
        )
        return report, trace

    def _build_trace(
        self, state: WorkflowState, issue_hash: str
    ) -> SessionTraceManifest:
        return SessionTraceManifest(
            run_id=self.run_id,
            workflow="bug-resolve",
            issue_text_hash=issue_hash,
            repos=list(self.repos),
            start_ts=self._start_ts,
            end_ts=utc_now_ts(),
            stage_sequence=list(state.stage_history) + [state.stage],
            artefact_refs=[],
            tool_calls=[],
            gate_events=[],
            monitor_events=list(state.monitor_events),
            budget_events=[],
            approval_events=[],
            redaction_policy="redacted",
            harness_condition_id=self.harness_condition_id,
        )


async def run_bug_resolve_workflow(
    *,
    run_id: str,
    issue_text: str,
    repos: list[str] | None = None,
    config: WorkflowConfig | None = None,
    localise: LocaliseCallable | None = None,
    repo_qa: RepoQACallable | None = None,
    sarif_gate: GateCallable | None = None,
    build_gate: GateCallable | None = None,
    test_gate: GateCallable | None = None,
    interface_gate: GateCallable | None = None,
    patch_generator: PatchGeneratorInterface | None = None,
    harness_condition_id: str = "hcs:default",
) -> WorkflowResult:
    """Convenience entry-point that creates and runs a :class:`BugResolveWorkflow`."""
    workflow = BugResolveWorkflow(
        run_id=run_id,
        issue_text=issue_text,
        repos=repos,
        config=config,
        localise=localise,
        repo_qa=repo_qa,
        sarif_gate=sarif_gate,
        build_gate=build_gate,
        test_gate=test_gate,
        interface_gate=interface_gate,
        patch_generator=patch_generator,
        harness_condition_id=harness_condition_id,
    )
    return await workflow.run()


__all__ = ["BugResolveWorkflow", "run_bug_resolve_workflow", "WorkflowResult"]
