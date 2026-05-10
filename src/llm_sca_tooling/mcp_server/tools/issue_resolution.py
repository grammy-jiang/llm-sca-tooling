"""Phase 13 run_issue_resolution MCP tool handler."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from llm_sca_tooling.blast_radius.service import BlastRadiusService
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import (
    ArtifactKind,
    PermissionMode,
    RedactionStatus,
    SideEffectClass,
)
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.workflows.bug_resolve.config import WorkflowConfig
from llm_sca_tooling.workflows.bug_resolve.state_machine import (
    run_bug_resolve_workflow,
)


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _store_artifact(context: McpRequestContext, payload: str, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    artifact_dir = context.workspace.artifact_root / "bug_resolve"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{kind}_{digest[:24]}.json"
    path.write_text(payload + "\n", encoding="utf-8")
    ref = ArtifactRef(
        artifact_id=f"art:bug-resolve-{kind}:{digest[:24]}",
        kind=ArtifactKind.REPORT,
        uri=str(path),
        sha256=digest,
        size_bytes=path.stat().st_size,
        media_type="application/json",
        redaction_status=RedactionStatus.REDACTED,
        created_ts=_now_ts(),
    )
    return context.workspace.artifacts.record_artifact(
        ref, repo_id=None, payload_path=Path(path)
    )


_RUN_ISSUE_RESOLUTION_INPUT = _schema(
    {
        "issue_text": {"type": "string"},
        "repos": {"type": "array", "items": {"type": "string"}},
        "budget": {"type": "object"},
        "config": {"type": "object"},
        "null_mode": {"type": "boolean"},
        "run_id": {"type": "string"},
        "task": {"type": "object"},
    },
    ["issue_text"],
)


class RunIssueResolutionTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_issue_resolution",
        description=(
            "Phase 13 bug-resolve workflow entrypoint. Runs the ten-stage "
            "investigate -> repair -> dryrun -> gates -> patch_risk -> "
            "blast_radius -> scope_audit -> operational_review -> trajectory "
            "pipeline and returns a BugResolveReport with HarnessConditionSheet "
            "reference."
        ),
        input_schema=_RUN_ISSUE_RESOLUTION_INPUT,
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=True,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        issue_text = args.get("issue_text")
        if not isinstance(issue_text, str) or not issue_text.strip():
            raise ToolInvalidArguments("issue_text is required")

        repos_raw = args.get("repos")
        repos: list[str] | None = None
        if isinstance(repos_raw, list):
            repos = [str(r) for r in repos_raw]

        null_mode = bool(args.get("null_mode", True))
        run_id_raw = args.get("run_id")
        if isinstance(run_id_raw, str) and run_id_raw:
            run_id = run_id_raw
        else:
            run_id = (
                f"run:{hashlib.sha256(issue_text.encode('utf-8')).hexdigest()[:16]}"
            )

        config = WorkflowConfig(null_mode=null_mode)

        report, state, trace = asyncio.run(
            run_bug_resolve_workflow(
                run_id=run_id,
                issue_text=issue_text,
                repos=repos,
                config=config,
                blast_radius_service=BlastRadiusService(context.workspace.graph),
            )
        )

        report_payload = report.model_dump_json(indent=2)
        artifact = _store_artifact(context, report_payload, "report")

        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "report": report.model_dump(mode="json"),
                "state": {
                    "status": state.status.value,
                    "stage": state.stage.value,
                },
                "trace": {
                    "run_id": trace.run_id,
                    "stage_sequence": [s.value for s in trace.stage_sequence],
                },
            },
            artifact_refs=[artifact],
        )


__all__ = ["RunIssueResolutionTool"]
