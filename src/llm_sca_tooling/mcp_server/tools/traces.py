"""Phase 16 dynamic trace MCP tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass
from llm_sca_tooling.storage.errors import RepositoryNotFoundError
from llm_sca_tooling.traces.models import ScopeFilter
from llm_sca_tooling.traces.service import TraceCaptureOutput, capture_trace


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_INPUT = _schema(
    {
        "script": {"type": "string"},
        "args": {"type": "array", "items": {"type": "string"}},
        "repo": {"type": "string"},
        "repo_path": {"type": "string"},
        "working_dir": {"type": "string"},
        "scope_filter": {"type": "object"},
        "suspects": {"type": "array", "items": {"type": "string"}},
        "changed_symbols": {"type": "array", "items": {"type": "string"}},
        "timeout_seconds": {"type": "integer"},
        "language": {"type": "string"},
        "pre_fix": {"type": "boolean"},
        "post_fix": {"type": "boolean"},
        "null_mode": {"type": "boolean"},
        "expected_failure": {"type": "boolean"},
        "expected_exception_type": {"type": "string"},
        "max_raw_trace_bytes": {"type": "integer"},
        "max_compressed_events": {"type": "integer"},
        "task": {"type": "boolean"},
    },
    ["script"],
)


class CaptureTraceTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="capture_trace",
        description=(
            "Execute a scoped dynamic trace run. Raw trace events are stored as "
            "artefacts; tool output includes only typed run metadata and a "
            "compressed trace summary."
        ),
        input_schema=_INPUT,
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.EXECUTE,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.EXECUTES_CODE,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=True,
        ),
    )

    def __init__(self, task_runner: TaskRunner | None = None) -> None:
        self.task_runner = task_runner

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        _script(args)
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
                artifact_refs=(
                    [record.result_artifact_ref] if record.result_artifact_ref else []
                ),
            )
        output = self._run(context, args)
        return ToolResult(
            tool_name=self.descriptor.name,
            status=output.result.status.value,
            payload=_output_payload(output),
            artifact_refs=output.artifact_refs,
            diagnostics=output.result.diagnostics,
        )

    def _payload(self, context: McpRequestContext, args: JsonObject) -> JsonObject:
        return _output_payload(self._run(context, args))

    def _run(self, context: McpRequestContext, args: JsonObject) -> TraceCaptureOutput:
        repo_id, root = _repo_root(context, args)
        working_dir = Path(str(args.get("working_dir") or root)).expanduser().resolve()
        try:
            return asyncio.run(
                capture_trace(
                    script=_script(args),
                    args=_str_list(args, "args"),
                    working_dir=working_dir,
                    allowed_roots=[root],
                    scope_filter=_scope(args),
                    suspects=_str_list(args, "suspects"),
                    changed_symbols=_str_list(args, "changed_symbols"),
                    timeout_seconds=int(args.get("timeout_seconds") or 30),
                    language=str(args.get("language") or "python"),
                    expected_failure=bool(args.get("expected_failure", False)),
                    expected_exception_type=_opt_str(args, "expected_exception_type"),
                    max_raw_trace_bytes=int(
                        args.get("max_raw_trace_bytes") or 1_000_000
                    ),
                    max_compressed_events=int(args.get("max_compressed_events") or 50),
                    null_mode=bool(args.get("null_mode", True)),
                    artifact_root=context.workspace.artifact_root,
                    artifact_store=context.workspace.artifacts,
                    repo_id=repo_id,
                    graph=context.workspace.graph,
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise ToolInvalidArguments(str(exc)) from exc


def _output_payload(output: TraceCaptureOutput) -> JsonObject:
    payload: JsonObject = {
        "result": output.result.model_dump(mode="json"),
        "harness_condition": output.harness_condition.model_dump(mode="json"),
    }
    if output.compressed_trace is not None:
        payload["compressed_trace"] = output.compressed_trace.model_dump(mode="json")
    return payload


def _script(args: JsonObject) -> str:
    script = args.get("script")
    if not isinstance(script, str) or not script.strip():
        raise ToolInvalidArguments("script is required")
    return script


def _opt_str(args: JsonObject, key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInvalidArguments(f"{key} must be a string")
    return value


def _str_list(args: JsonObject, key: str) -> list[str] | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolInvalidArguments(f"{key} must be a list of strings")
    return [str(item) for item in value]


def _scope(args: JsonObject) -> ScopeFilter | JsonObject | None:
    value = args.get("scope_filter")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolInvalidArguments("scope_filter must be an object")
    return dict(value)


def _repo_root(context: McpRequestContext, args: JsonObject) -> tuple[str | None, Path]:
    repo = args.get("repo")
    if isinstance(repo, str) and repo:
        try:
            row = context.workspace.repositories.get_repo(repo)
        except RepositoryNotFoundError as exc:
            raise ToolInvalidArguments(str(exc)) from exc
        return row.repo_id, Path(row.root_path).resolve()
    repo_path = args.get("repo_path")
    if isinstance(repo_path, str) and repo_path:
        return None, Path(repo_path).expanduser().resolve()
    script_path = Path(_script(args)).expanduser().resolve()
    return None, script_path.parent
