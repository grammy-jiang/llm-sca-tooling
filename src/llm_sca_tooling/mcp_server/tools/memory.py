"""Phase 17 governed memory MCP tools."""

from __future__ import annotations

import uuid

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.memory.eviction.compactor import MemoryCompactor
from llm_sca_tooling.memory.models import (
    LessonTargetType,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.promotion.pipeline import promote_operational_lesson
from llm_sca_tooling.memory.retrieval.sqlite_retriever import SqliteMemoryRetriever
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.memory.write_path import write_trajectory
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


class RetrieveMemoryTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="retrieve_memory",
        description="Retrieve governed soft memory hints for investigation, repair, or review.",
        input_schema=_schema(
            {
                "issue_text": {"type": "string"},
                "phase": {"type": "string"},
                "repo": {"type": "string"},
                "graph_node_ids": {"type": "array", "items": {"type": "string"}},
                "max_hints": {"type": "integer"},
            },
            ["issue_text", "phase", "repo"],
        ),
        output_schema={"type": "object"},
        read_only=True,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="workspace_memory",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=False,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        store = MemoryStore(context.workspace.conn)
        policy = store.get_policy()
        repo_id = _required_str(args, "repo")
        if not policy.repo_enabled(repo_id):
            return ToolResult(
                tool_name=self.descriptor.name,
                status="memory_disabled",
                payload={
                    "status": "memory_disabled",
                    "hints": [],
                    "rejected": [],
                    "memory_hint_weight": 0.0,
                },
            )
        issue_text = _required_str(args, "issue_text")
        phase = _required_str(args, "phase")
        max_hints = int(args.get("max_hints") or 5)
        retriever = SqliteMemoryRetriever(store)
        if phase == "investigate":
            hints, rejected = retriever.retrieve_coarse(
                issue_text=issue_text, repo_id=repo_id, phase=phase, max_hints=max_hints
            )
            hint_payloads = [hint.model_dump(mode="json") for hint in hints]
            rejected_payloads = [hint.model_dump(mode="json") for hint in rejected]
        else:
            fine_hints, fine_rejected = retriever.retrieve_fine(
                issue_text=issue_text,
                repo_id=repo_id,
                phase=phase,
                graph_node_ids=_str_list(args, "graph_node_ids"),
                max_hints=max_hints,
            )
            hint_payloads = [hint.model_dump(mode="json") for hint in fine_hints]
            rejected_payloads = [hint.model_dump(mode="json") for hint in fine_rejected]
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "status": "available",
                "phase": phase,
                "hints": hint_payloads,
                "rejected": rejected_payloads,
                "memory_hint_weight": 0.0,
            },
        )


class RecordTrajectoryTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="record_trajectory",
        description="Write a schema-grounded workflow trajectory through governed memory gates.",
        input_schema=_schema(
            {
                "repo": {"type": "string"},
                "workflow_type": {"type": "string"},
                "issue_class": {"type": "string"},
                "issue_text_hash": {"type": "string"},
                "fl_decisions": {"type": "array", "items": {"type": "object"}},
                "graph_node_ids": {"type": "array", "items": {"type": "string"}},
                "graph_snapshot_id": {"type": "string"},
                "patch_diff_hash": {"type": "string"},
                "patch_class": {"type": "string"},
                "sarif_delta_summary": {"type": "object"},
                "test_delta_summary": {"type": "object"},
                "outcome": {"type": "string"},
                "utility": {"type": "string"},
                "bounded_snippet_ids": {"type": "array", "items": {"type": "string"}},
                "source_run_id": {"type": "string"},
                "source_trace_manifest_id": {"type": "string"},
            },
            [
                "repo",
                "workflow_type",
                "issue_class",
                "issue_text_hash",
                "graph_snapshot_id",
                "outcome",
                "source_run_id",
            ],
        ),
        output_schema={"type": "object"},
        read_only=False,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="workspace_memory",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        store = MemoryStore(context.workspace.conn)
        trajectory = _trajectory(args)
        result = write_trajectory(
            store=store,
            policy=store.get_policy(),
            trajectory=trajectory,
            graph=context.workspace.graph,
        )
        status = "completed" if result.written else "rejected"
        if any(item.startswith("MemoryDisabled") for item in result.gate_failures):
            status = "memory_disabled"
        return ToolResult(
            tool_name=self.descriptor.name,
            status=status,
            payload={
                "write_path": result.model_dump(mode="json"),
                "trajectory": (
                    trajectory.model_dump(mode="json") if result.written else None
                ),
            },
            diagnostics=result.diagnostics,
        )


class MemoryCompactTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="memory_compact",
        description="Apply deterministic memory eviction and retention policy.",
        input_schema=_schema(
            {
                "repo": {"type": "string"},
                "dry_run": {"type": "boolean"},
                "task": {"type": "boolean"},
            }
        ),
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.EXECUTE,
            path_scope="workspace_memory",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def __init__(
        self,
        task_runner: TaskRunner | None = None,
        notifications: NotificationManager | None = None,
    ) -> None:
        self.task_runner = task_runner
        self.notifications = notifications

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
                artifact_refs=(
                    [record.result_artifact_ref] if record.result_artifact_ref else []
                ),
            )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=self._payload(context, args),
        )

    def _payload(self, context: McpRequestContext, args: JsonObject) -> JsonObject:
        store = MemoryStore(context.workspace.conn)
        repo_id = _opt_str(args, "repo")
        if not store.get_policy().enabled:
            return {"status": "memory_disabled"}
        report = MemoryCompactor(store).compact(
            repo_id=repo_id, dry_run=bool(args.get("dry_run", True))
        )
        if self.notifications is not None and repo_id:
            self.notifications.resources_updated(
                f"code-intelligence://memory/{repo_id}/trajectories",
                payload={"report_id": report.report_id},
            )
        return {"status": "completed", "report": report.model_dump(mode="json")}


class PromoteOperationalLessonTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="promote_operational_lesson",
        description="Promote a reviewed operational lesson to governed memory or another target.",
        input_schema=_schema(
            {
                "repo": {"type": "string"},
                "source_run_id": {"type": "string"},
                "source_event_id": {"type": "string"},
                "target_type": {"type": "string"},
                "structured_content": {"type": "object"},
                "owner": {"type": "string"},
                "expiry_ts": {"type": "string"},
                "rollback_path": {"type": "string"},
                "review_approved": {"type": "boolean"},
            },
            [
                "repo",
                "source_run_id",
                "source_event_id",
                "target_type",
                "structured_content",
                "owner",
                "rollback_path",
            ],
        ),
        output_schema={"type": "object"},
        read_only=False,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.REVIEW,
            path_scope="workspace_memory",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        store = MemoryStore(context.workspace.conn)
        try:
            lesson, promoted = promote_operational_lesson(
                store=store,
                policy=store.get_policy(),
                repo_id=_required_str(args, "repo"),
                source_run_id=_required_str(args, "source_run_id"),
                source_event_id=_required_str(args, "source_event_id"),
                target_type=LessonTargetType(_required_str(args, "target_type")),
                structured_content=_dict(args, "structured_content"),
                owner=_required_str(args, "owner"),
                expiry_ts=_opt_str(args, "expiry_ts"),
                rollback_path=_required_str(args, "rollback_path"),
                review_approved=bool(args.get("review_approved", False)),
            )
        except ValueError as exc:
            status = "memory_disabled" if "MemoryDisabled" in str(exc) else "rejected"
            return ToolResult(
                tool_name=self.descriptor.name,
                status=status,
                payload={"status": status, "diagnostic": str(exc)},
            )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "lesson": lesson.model_dump(mode="json"),
                "promoted_record": (
                    promoted.model_dump(mode="json") if promoted else None
                ),
            },
        )


def _trajectory(args: JsonObject) -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=f"traj:{uuid.uuid4().hex}",
        repo_id=_required_str(args, "repo"),
        workflow_type=_required_str(args, "workflow_type"),
        issue_class=_required_str(args, "issue_class"),
        issue_text_hash=_required_str(args, "issue_text_hash"),
        fl_decisions=_dict_list(args, "fl_decisions"),
        graph_node_ids=_str_list(args, "graph_node_ids") or [],
        graph_snapshot_id=_required_str(args, "graph_snapshot_id"),
        patch_diff_hash=_opt_str(args, "patch_diff_hash"),
        patch_class=_opt_str(args, "patch_class"),
        sarif_delta_summary=_dict(args, "sarif_delta_summary", default={}),
        test_delta_summary=_dict(args, "test_delta_summary", default={}),
        outcome=TrajectoryOutcome(_required_str(args, "outcome")),
        utility=TrajectoryUtility(
            str(args.get("utility") or TrajectoryUtility.UNKNOWN.value)
        ),
        bounded_snippet_ids=_str_list(args, "bounded_snippet_ids") or [],
        source_run_id=_required_str(args, "source_run_id"),
        source_trace_manifest_id=_opt_str(args, "source_trace_manifest_id"),
    )


def _required_str(args: JsonObject, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInvalidArguments(f"{key} is required")
    return value


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
        raise ToolInvalidArguments(f"{key} must be a list")
    return [str(item) for item in value]


def _dict(
    args: JsonObject, key: str, *, default: JsonObject | None = None
) -> JsonObject:
    value = args.get(key, default)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ToolInvalidArguments(f"{key} must be an object")
    return dict(value)


def _dict_list(args: JsonObject, key: str) -> list[JsonObject]:
    value = args.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ToolInvalidArguments(f"{key} must be a list")
    return [dict(item) for item in value if isinstance(item, dict)]
