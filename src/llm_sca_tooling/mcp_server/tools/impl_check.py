"""Phase 14 run_implementation_check MCP tool handler."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

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
from llm_sca_tooling.workflows.impl_check.report import (
    run_implementation_check as _run_impl_check,
)

_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "spec": {"type": "string"},
        "repos": {"type": "array", "items": {"type": "string"}},
        "policy": {"type": "object"},
        "null_mode": {"type": "boolean"},
        "run_id": {"type": "string"},
    },
    "required": ["spec"],
    "additionalProperties": False,
}


class RunImplementationCheckTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_implementation_check",
        description=(
            "Phase 14 implementation-check workflow entrypoint. Runs the seven-stage "
            "DAG (spec ingestion -> clause extraction -> intent graph -> contract "
            "generation -> grounding -> static verdict -> aggregation) and returns an "
            "ImplementationCheckReport with ClauseVerdictMatrix."
        ),
        input_schema=_SCHEMA,
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
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        spec = args.get("spec")
        if not isinstance(spec, str) or not spec.strip():
            raise ToolInvalidArguments("spec is required")

        run_id_raw = args.get("run_id")
        if run_id_raw is not None and not isinstance(run_id_raw, str):
            raise ToolInvalidArguments("run_id must be a string")

        null_mode = bool(args.get("null_mode", True))

        report, matrix = asyncio.run(
            _run_impl_check(
                spec=spec,
                run_id=run_id_raw or None,
                null_mode=null_mode,
            )
        )

        report_payload = report.model_dump_json(indent=2)
        digest = hashlib.sha256(report_payload.encode("utf-8")).hexdigest()
        artifact_dir = context.workspace.artifact_root / "impl_check"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"report_{digest[:24]}.json"
        path.write_text(report_payload + "\n", encoding="utf-8")

        ref = ArtifactRef(
            artifact_id=f"art:impl-check-report:{digest[:24]}",
            kind=ArtifactKind.REPORT,
            uri=str(path),
            sha256=digest,
            size_bytes=path.stat().st_size,
            media_type="application/json",
            redaction_status=RedactionStatus.REDACTED,
            created_ts=_now_ts(),
        )
        artifact = context.workspace.artifacts.record_artifact(
            ref, repo_id=None, payload_path=Path(path)
        )

        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "report": report.model_dump(mode="json"),
                "clause_verdict_matrix": matrix.model_dump(mode="json"),
            },
            artifact_refs=[artifact],
        )


__all__ = ["RunImplementationCheckTool"]
