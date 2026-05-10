"""Phase 9 fault-localisation MCP tools."""

from __future__ import annotations

import hashlib
from pathlib import Path

from llm_sca_tooling.fl.localisation import (
    LocalisationRequest,
    LocalisationResult,
    LocalisationService,
)
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


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


class GetRelevantFilesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="get_relevant_files",
        description="Rank likely root-cause files for an issue using Phase 9 multi-signal fault localisation.",
        input_schema=_schema(
            {
                "issue_text": {"type": "string"},
                "repos": {"type": "array", "items": {"type": "string"}},
                "failing_tests": {"type": "array", "items": {"type": "string"}},
                "coverage_path": {"type": "string"},
                "max_files": {"type": "integer"},
                "include_symbols": {"type": "boolean"},
                "snapshot": {"type": "string"},
                "use_embedding": {"type": "boolean"},
                "budget": {"type": "object"},
            },
            ["issue_text"],
        ),
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
        issue_text = args.get("issue_text")
        if not isinstance(issue_text, str) or not issue_text.strip():
            raise ToolInvalidArguments("issue_text is required")
        request = LocalisationRequest(
            issue_text=issue_text,
            repos=_string_list(args.get("repos")),
            failing_tests=_string_list(args.get("failing_tests")),
            coverage_path=(
                str(args["coverage_path"]) if args.get("coverage_path") else None
            ),
            max_files=int(args["max_files"]) if args.get("max_files") else None,
            include_symbols=bool(args.get("include_symbols", False)),
            snapshot=str(args["snapshot"]) if args.get("snapshot") else None,
            use_embedding=bool(args.get("use_embedding", True)),
            budget=args.get("budget") if isinstance(args.get("budget"), dict) else None,
        )
        result = LocalisationService(context.workspace).get_relevant_files(request)
        artifact_ref = _store_context_bundle(context, result)
        result = result.model_copy(update={"context_bundle_ref": artifact_ref})
        payload = result.model_dump(mode="json", exclude={"context_bundle"})
        payload["repo_id"] = (
            result.ranked_files[0].repo_id if result.ranked_files else None
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=payload,
            artifact_refs=[artifact_ref] if artifact_ref else [],
            diagnostics=result.diagnostics,
            run_event_ids=result.run_event_ids,
        )


def _store_context_bundle(
    context: McpRequestContext, result: LocalisationResult
) -> ArtifactRef | None:
    if result.context_bundle is None:
        return None
    payload = result.context_bundle.model_dump_json(indent=2)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    artifact_dir = context.workspace.artifact_root / "fl"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"context_bundle_{digest[:24]}.json"
    path.write_text(payload + "\n", encoding="utf-8")
    ref = ArtifactRef(
        artifact_id=f"art:fl-context:{digest[:24]}",
        kind=ArtifactKind.REPORT,
        uri=str(path),
        sha256=digest,
        size_bytes=path.stat().st_size,
        media_type="application/json",
        redaction_status=RedactionStatus.REDACTED,
        created_ts=_now_ts(),
    )
    repo_id = result.ranked_files[0].repo_id if result.ranked_files else None
    return context.workspace.artifacts.record_artifact(
        ref,
        repo_id=repo_id,
        payload_path=Path(path),
    )


def _string_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolInvalidArguments("expected a list of strings")
    return [str(item) for item in value]
