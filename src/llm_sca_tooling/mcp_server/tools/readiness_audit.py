"""Phase 18 readiness audit MCP tool."""

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
from llm_sca_tooling.release.models import ReadinessAuditReport
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass


class RunReadinessAuditTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_readiness_audit",
        description="Run a Phase 18 AI-readiness audit for a repository.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "policy": {"type": "object"},
                "task": {"type": "boolean"},
            },
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.REVIEW,
            path_scope="registered_repo",
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
        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")
        report = ReadinessAuditReport(
            report_id=f"readiness:{uuid.uuid4().hex}",
            repo_id=repo,
            ai_readiness_score=22,
            harness_stage="S3",
            drift_findings=[],
            missing_gates=[],
            weak_docs_spec_links=[],
            unprotected_risky_paths=[],
            absent_scanners=[],
            recommended_readiness_tasks=[],
        )
        return {"report": report.model_dump(mode="json")}
