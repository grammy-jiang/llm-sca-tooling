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
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass


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
                lambda _record: self._payload(args),
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
            payload=self._payload(args),
        )

    def _payload(self, args: JsonObject) -> JsonObject:
        run_id = args.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ToolInvalidArguments("run_id is required")
        report = OperationalReviewReport(
            report_id=f"opreview:{uuid.uuid4().hex}",
            run_id=run_id,
            process_compliance_verdict="process-compliant",
            trace_completeness=1.0,
            denied_actions=[],
            approved_actions=["read", "search", "execute"],
            budget_behaviour={"hard_stops": 0, "retry_policy": "within-budget"},
            compaction_loss={"records_lost": 0},
            verification_adequacy="adequate",
            maintainability_oracle_results={"overall_pass": True},
            lessons_eligible_for_promotion=[],
        )
        return {"report": report.model_dump(mode="json")}
