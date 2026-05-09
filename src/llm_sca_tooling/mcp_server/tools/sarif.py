"""SARIF static-analysis MCP tool."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments, ToolUnavailable
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.sarif.errors import AnalyserUnavailableError
from llm_sca_tooling.sarif.pipeline import StaticAnalysisRunner
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass
from llm_sca_tooling.storage.errors import RepositoryNotFoundError


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


class RunStaticAnalysisTool(ToolHandler):
    def __init__(
        self, task_runner: TaskRunner, notifications: NotificationManager
    ) -> None:
        self.task_runner = task_runner
        self.notifications = notifications

    descriptor = ToolDescriptor(
        name="run_static_analysis",
        description="Run or import static-analysis SARIF, bind alerts to graph nodes, and emit warned_by edges.",
        input_schema=_schema(
            {
                "repo": {"type": "string"},
                "analyser": {"type": "string"},
                "ruleset": {},
                "files": {"type": "array", "items": {"type": "string"}},
                "snapshot": {"type": "string"},
                "import_sarif_path": {"type": "string"},
                "config": {"type": "object"},
                "task": {"type": "boolean"},
            },
            ["repo", "analyser"],
        ),
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
        emits_resource_notifications=True,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = _repo(context, args.get("repo"))
        analyser = args.get("analyser")
        if not isinstance(analyser, str) or not analyser:
            raise ToolInvalidArguments("analyser is required")

        def executor(record=None):
            try:
                result = StaticAnalysisRunner(context.workspace).run(
                    repo=repo,
                    analyser=analyser,
                    ruleset=args.get("ruleset"),
                    files=[str(item) for item in args.get("files") or []] or None,
                    import_sarif_path=args.get("import_sarif_path"),
                    config=args.get("config") or {},
                    produced_by_run_id=record.task_id if record else None,
                )
            except AnalyserUnavailableError as exc:
                raise ToolUnavailable(str(exc)) from exc
            run = result["run"]
            uri = f"code-intelligence://sarif/{repo.repo_id}/{run.run_id}"
            updates = [
                uri,
                f"code-intelligence://sarif/{repo.repo_id}",
                f"code-intelligence://graph/{repo.repo_id}",
            ]
            notifications = self.notifications.resources_updated(
                *updates, payload={"repo_id": repo.repo_id, "run_id": run.run_id}
            )
            return {
                "run_id": run.run_id,
                "repo_id": repo.repo_id,
                "status": "completed",
                "alert_count": len(run.alerts),
                "rule_count": len(run.rules),
                "new_critical_high_count": result["new_critical_high_count"],
                "delta_from_run_id": run.delta_from_run_id,
                "delta_id": result["delta_id"],
                "sarif_resource_uri": uri,
                "run_event_ids": [],
                "diagnostics": result["diagnostics"],
                "resource_updates": updates,
                "notifications": [
                    notification.model_dump(mode="json")
                    for notification in notifications
                ],
                "bound_alert_count": result["bound_alert_count"],
                "symbol_bound_alert_count": result["symbol_bound_alert_count"],
                "warned_by_edge_count": result["edges_emitted"],
            }

        if bool(args.get("task")):
            record = self.task_runner.start(
                self.descriptor.name,
                args,
                executor,
                authorization_context_hash=context.authorization_context_hash,
                metadata={"repo_id": repo.repo_id},
            )
            return ToolResult(
                tool_name=self.descriptor.name,
                status="task_created",
                payload={"task": record.model_dump(mode="json")},
                artifact_refs=(
                    [record.result_artifact_ref] if record.result_artifact_ref else []
                ),
                notifications=[
                    notification.model_dump(mode="json")
                    for notification in self.notifications.all()
                ],
            )
        payload = executor()
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=payload,
            notifications=payload["notifications"],
            diagnostics=[{"message": item} for item in payload["diagnostics"]],
        )


def _repo(context: McpRequestContext, repo_id_or_name: object):
    if not isinstance(repo_id_or_name, str) or not repo_id_or_name:
        raise ToolInvalidArguments("repo is required")
    try:
        return context.workspace.repositories.get_repo(repo_id_or_name)
    except RepositoryNotFoundError as exc:
        raise ToolInvalidArguments(str(exc)) from exc
