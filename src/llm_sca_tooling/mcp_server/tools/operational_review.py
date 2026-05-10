"""Phase 18 operational review MCP tool."""

from __future__ import annotations

import uuid

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.release.models import OperationalReviewReport
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, PolicyAction, SideEffectClass
from llm_sca_tooling.storage.errors import RunNotFoundError


class RunOperationalReviewTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_operational_review",
        description="Run a Phase 18 operational review over a stored run record.",
        input_schema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "policy": {"type": "object"},
                "task": {"type": "boolean"},
            },
            "required": ["run_id"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.REVIEW,
            path_scope="workspace_operational_store",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=False,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def __init__(self, task_runner: TaskRunner | None = None) -> None:
        self.task_runner = task_runner

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        if args.get("task") and self.task_runner is not None:
            record = self.task_runner.start(
                self.descriptor.name,
                args,
                lambda _record: self._payload(context, args),
                authorization_context_hash=context.authorization_context_hash,
            )
            return ToolResult(
                tool_name=self.descriptor.name,
                status="task_created",
                payload={"task": record.model_dump(mode="json")},
            )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=self._payload(context, args),
        )

    def _payload(self, context: McpRequestContext, args: JsonObject) -> JsonObject:
        run_id = args.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ToolInvalidArguments("run_id is required")
        try:
            view = context.workspace.operations.get_run(run_id, include_events=True)
        except RunNotFoundError:
            report = OperationalReviewReport(
                report_id=f"opreview:{uuid.uuid4().hex}",
                run_id=run_id,
                process_compliance_verdict="trace-incomplete",
                trace_completeness=0.0,
                denied_actions=[],
                approved_actions=[],
                budget_behaviour={"diagnostic": "run_not_found"},
                compaction_loss={"records_lost": "unknown"},
                verification_adequacy="missing-run-record",
                maintainability_oracle_results={"overall_pass": False},
                lessons_eligible_for_promotion=[],
            )
            return {"report": report.model_dump(mode="json")}

        run = view.run
        events = view.events
        expected = run.run_event_count
        trace_completeness = 1.0 if expected == 0 else min(1.0, len(events) / expected)
        denied_actions = [
            event.stage
            for event in events
            if event.policy_action in {PolicyAction.DENY, PolicyAction.BLOCKED}
        ]
        approved_actions = [
            event.stage for event in events if event.policy_action == PolicyAction.ALLOW
        ]
        hard_stops = [
            event
            for event in events
            if event.type.value in {"budget_hard_stop", "tool_call_failed"}
        ]
        verification_events = [
            event
            for event in events
            if event.type.value
            in {
                "verification_started",
                "verification_completed",
                "final_verdict_recorded",
            }
        ]
        if run.status.value in {"failed", "blocked", "cancelled"}:
            verdict = "process-noncompliant"
        elif trace_completeness < 1.0:
            verdict = "trace-incomplete"
        elif hard_stops:
            verdict = "budget-exhausted"
        elif denied_actions:
            verdict = "process-noncompliant"
        else:
            verdict = "process-compliant"
        verification_adequacy = (
            "adequate"
            if verification_events or run.final_verdict_id
            else "no-verification-evidence"
        )
        report = OperationalReviewReport(
            report_id=f"opreview:{uuid.uuid4().hex}",
            run_id=run_id,
            process_compliance_verdict=verdict,
            trace_completeness=trace_completeness,
            denied_actions=denied_actions,
            approved_actions=approved_actions,
            budget_behaviour={
                "hard_stops": len(hard_stops),
                "status": run.status.value,
            },
            compaction_loss={"records_lost": 0},
            verification_adequacy=verification_adequacy,
            maintainability_oracle_results={
                "overall_pass": verification_adequacy == "adequate"
            },
            lessons_eligible_for_promotion=[],
        )
        return {"report": report.model_dump(mode="json")}
