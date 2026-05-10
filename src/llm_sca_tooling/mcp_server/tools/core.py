"""Phase 4 graph and registry tool handlers."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.resource_uris import decode_repo_relative_path
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.mcp_server.tools.blame import (
    GitBlameChainTool as Phase8GitBlameChainTool,
)
from llm_sca_tooling.mcp_server.tools.eval import (
    ComputeRdsFeaturesTool,
    RecordEvalResultTool,
    RunEvalSuiteTool,
)
from llm_sca_tooling.mcp_server.tools.fl import GetRelevantFilesTool
from llm_sca_tooling.mcp_server.tools.impl_check import (
    RunImplementationCheckTool,
)
from llm_sca_tooling.mcp_server.tools.interface import (
    PluginReloadTool as InterfacePluginReloadTool,
)
from llm_sca_tooling.mcp_server.tools.interface import (
    TraceCrossLanguageTool,
)
from llm_sca_tooling.mcp_server.tools.issue_resolution import (
    RunIssueResolutionTool,
)
from llm_sca_tooling.mcp_server.tools.memory import (
    MemoryCompactTool,
    PromoteOperationalLessonTool,
    RecordTrajectoryTool,
    RetrieveMemoryTool,
)
from llm_sca_tooling.mcp_server.tools.operational_review import (
    RunOperationalReviewTool,
)
from llm_sca_tooling.mcp_server.tools.patch_review import (
    ClassifyPatchRiskTool,
    RunPatchReviewTool,
)
from llm_sca_tooling.mcp_server.tools.qa import (
    AnswerRepoQuestionTool,
    ClassifyRepoQuestionTool,
    GetInterfaceContractTool,
)
from llm_sca_tooling.mcp_server.tools.readiness_audit import RunReadinessAuditTool
from llm_sca_tooling.mcp_server.tools.sarif import RunStaticAnalysisTool
from llm_sca_tooling.mcp_server.tools.sast_repair import (
    EvolveStaticRulesTool,
    GetPredicateExamplesTool,
    RunSastRepairTool,
)
from llm_sca_tooling.mcp_server.tools.traces import CaptureTraceTool
from llm_sca_tooling.plugins.capability import TraversalDirection
from llm_sca_tooling.plugins.registry import default_plugin_registry
from llm_sca_tooling.plugins.traversal import CrossLanguageTraverser
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import GraphEdgeType, PermissionMode, SideEffectClass
from llm_sca_tooling.storage.errors import (
    RepositoryNotFoundError,
)


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _descriptor(
    name: str,
    description: str,
    input_schema: JsonObject,
    *,
    read_only: bool,
    long_running: bool = False,
    task_support: str = "none",
    mode: PermissionMode = PermissionMode.READ,
    side_effect: SideEffectClass = SideEffectClass.READ_ONLY,
    writes_to_store: bool = False,
    runs_subprocesses: bool = False,
    notifications: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema={"type": "object"},
        read_only=read_only,
        long_running=long_running,
        task_support=task_support,
        permission=ToolPermissionDescriptor(
            required_mode=mode,
            path_scope=(
                "registered_repo" if name != "register_repo" else "target_repo_root"
            ),
            network_requirement="none",
            side_effect_class=side_effect,
            writes_to_store=writes_to_store,
            writes_to_repo=False,
            runs_subprocesses=runs_subprocesses,
        ),
        emits_resource_notifications=notifications,
    )


class RegisterRepoTool(ToolHandler):
    descriptor = _descriptor(
        "register_repo",
        "Register a local repository in the workspace without indexing it.",
        _schema(
            {
                "repo_path": {"type": "string"},
                "name": {"type": "string"},
                "policy_scope": {"type": "object"},
            },
            ["repo_path"],
        ),
        read_only=False,
        mode=PermissionMode.SEARCH,
        side_effect=SideEffectClass.READ_ONLY,
        writes_to_store=True,
        notifications=True,
    )

    def __init__(self, notifications: NotificationManager) -> None:
        self.notifications = notifications

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo_path = args.get("repo_path")
        if not isinstance(repo_path, str) or not repo_path.strip():
            raise ToolInvalidArguments("repo_path is required")
        repo = context.workspace.repositories.register_repo(
            repo_path, name=args.get("name"), policy_scope=args.get("policy_scope")
        )
        notification = self.notifications.resources_list_changed(
            {"repo_id": repo.repo_id}
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={"repository": repo.public_metadata()},
            notifications=[notification.model_dump(mode="json")],
        )


class GraphSliceTool(ToolHandler):
    descriptor = _descriptor(
        "get_graph_slice",
        "Return a bounded typed graph slice for files or symbols.",
        _schema(
            {
                "repo": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "depth": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            ["repo"],
        ),
        read_only=True,
        mode=PermissionMode.SEARCH,
        side_effect=SideEffectClass.NONE,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = _repo(context, args.get("repo"))
        depth = int(args.get("depth") or 1)
        limit = int(args.get("limit") or context.config.max_graph_slice_nodes)
        generator = GraphSliceGenerator(context.workspace)
        files = args.get("files") or []
        symbols = args.get("symbols") or []
        if files:
            file_path = decode_repo_relative_path(str(files[0]))
            graph_slice = generator.by_file(
                repo.repo_id, file_path, depth=depth, limit=limit
            )
        elif symbols:
            graph_slice = generator.by_symbol(
                repo.repo_id, str(symbols[0]), depth=depth, limit=limit
            )
        else:
            raise ToolInvalidArguments("files or symbols must be provided")
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={"graph_slice": graph_slice.model_dump(mode="json")},
        )


class CallGraphTool(ToolHandler):
    def __init__(self, *, callees: bool) -> None:
        self.callees = callees
        name = "find_callees" if callees else "find_callers"
        direction = "callees for" if callees else "callers of"
        self.descriptor = _descriptor(
            name,
            f"Return graph {direction} a symbol using calls edges.",
            _schema(
                {
                    "repo": {"type": "string"},
                    "symbol": {"type": "string"},
                    "depth": {"type": "integer"},
                    "include_cross_repo": {"type": "boolean"},
                    "include_cross_language": {"type": "boolean"},
                },
                ["repo", "symbol"],
            ),
            read_only=True,
            mode=PermissionMode.SEARCH,
            side_effect=SideEffectClass.NONE,
        )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = _repo(context, args.get("repo"))
        diagnostics = []
        if args.get("include_cross_repo"):
            diagnostics.append({"code": "cross_repo_requires_interface_plugins"})
        symbol = args.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise ToolInvalidArguments("symbol is required")
        nodes = context.workspace.graph.find_symbols(
            repo.repo_id, qualified_name=symbol
        )
        if not nodes:
            return ToolResult(
                tool_name=self.descriptor.name,
                status="completed",
                payload={
                    "matches": [],
                    "diagnostics": [{"code": "symbol_not_found", "symbol": symbol}],
                },
            )
        node_ids = {node.node_id for node in nodes}
        matches = []
        for node_id in node_ids:
            column = "source_id" if self.callees else "target_id"
            other = "target_id" if self.callees else "source_id"
            rows = context.workspace.conn.execute(
                f"SELECT payload_json, {other} FROM graph_edges WHERE {column}=? AND edge_type=?",
                (node_id, GraphEdgeType.CALLS.value),
            ).fetchall()
            for row in rows:
                target = context.workspace.graph.fetch_node(row[other])
                if target:
                    matches.append(
                        {
                            "edge": row["payload_json"],
                            "node": target.model_dump(mode="json"),
                        }
                    )
        if args.get("include_cross_language"):
            traverser = CrossLanguageTraverser(
                default_plugin_registry(), context.workspace.graph
            )
            direction = (
                TraversalDirection.OUTBOUND if self.callees else TraversalDirection.BOTH
            )
            for node_id in node_ids:
                trace = traverser.traverse(
                    node_id, direction=direction, max_hops=int(args.get("depth") or 3)
                )
                for reached in trace.reached_node_ids:
                    if reached == node_id:
                        continue
                    target = context.workspace.graph.fetch_node(reached)
                    if target:
                        matches.append(
                            {
                                "node": target.model_dump(mode="json"),
                                "cross_language": True,
                                "trace": trace.model_dump(mode="json"),
                            }
                        )
                diagnostics.extend({"code": code} for code in trace.diagnostics)
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={"symbol": symbol, "matches": matches, "diagnostics": diagnostics},
        )


class GitBlameChainTool(ToolHandler):
    descriptor = _descriptor(
        "git_blame_chain",
        "Return cached blame-chain evidence for a file, or a cache-miss diagnostic.",
        _schema(
            {
                "repo": {"type": "string"},
                "file": {"type": "string"},
                "line": {"type": "integer"},
            },
            ["repo", "file"],
        ),
        read_only=True,
        mode=PermissionMode.SEARCH,
        side_effect=SideEffectClass.NONE,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = _repo(context, args.get("repo"))
        file_path = decode_repo_relative_path(str(args.get("file")))
        resource_uri = f"code-intelligence://blame/{repo.repo_id}/{file_path}"
        from llm_sca_tooling.mcp_server.resources.core import BlameResource

        payload = (
            BlameResource()
            .read(
                context,
                resource_uri,
                type("Parsed", (), {"segments": (repo.repo_id, file_path)})(),
            )
            .payload
        )
        line = args.get("line")
        if line and payload.get("blame", {}).get("line_entries"):
            payload["blame"]["line_entries"] = [
                entry
                for entry in payload["blame"]["line_entries"]
                if entry.get("line_no") == int(line)
            ]
        return ToolResult(
            tool_name=self.descriptor.name, status="completed", payload=payload
        )


class PluginReloadTool(ToolHandler):
    descriptor = _descriptor(
        "plugin_reload",
        "Phase 4 placeholder for future interface plugin reloads.",
        _schema({"plugin_id": {"type": "string"}}),
        read_only=True,
        mode=PermissionMode.SEARCH,
        side_effect=SideEffectClass.NONE,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        return ToolResult(
            tool_name=self.descriptor.name,
            status="unavailable",
            payload={
                "status": "not_implemented_until_phase_7",
                "plugin_id": args.get("plugin_id"),
            },
        )


class GraphBuildTaskTool(ToolHandler):
    def __init__(
        self,
        *,
        update: bool,
        task_runner: TaskRunner,
        notifications: NotificationManager,
    ) -> None:
        self.update = update
        self.task_runner = task_runner
        self.notifications = notifications
        name = "graph_update" if update else "graph_build"
        self.descriptor = _descriptor(
            name,
            f"Start {'incremental update' if update else 'full build'} of repository graph as a persisted task.",
            _schema(
                {
                    "repo_path": {"type": "string"},
                    "repo_id": {"type": "string"},
                    "task": {"type": "boolean"},
                },
                [],
            ),
            read_only=False,
            long_running=True,
            task_support="optional",
            mode=PermissionMode.EXECUTE,
            side_effect=SideEffectClass.EXECUTES_CODE,
            writes_to_store=True,
            runs_subprocesses=True,
            notifications=True,
        )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo_path = _repo_path_for_args(context, args)
        repo_id_before = None
        try:
            repo_id_before = (
                context.workspace.repositories.get_repo(
                    args.get("repo_id") or Path(repo_path).name
                ).repo_id
                if args.get("repo_id")
                else None
            )
        except Exception:
            repo_id_before = None

        def executor(record):
            service = IndexingService(context.workspace)
            result = (
                service.graph_update(repo_path)
                if self.update
                else service.graph_build(repo_path)
            )
            updated_uris = [
                "code-intelligence://repos",
                f"code-intelligence://graph/{result.repo_id}",
                f"code-intelligence://build-evidence/{result.repo_id}",
            ]
            if self.update:
                updated_uris.extend(
                    f"code-intelligence://summary/{result.repo_id}/{path}"
                    for path in result.changed_files
                )
                updated_uris.extend(
                    f"code-intelligence://blame/{result.repo_id}/{path}"
                    for path in result.changed_files
                )
            self.notifications.resources_updated(
                *updated_uris,
                payload={"task_id": record.task_id, "run_id": result.run_id},
            )
            payload = result.model_dump(mode="json")
            payload["resource_updates"] = updated_uris
            return payload

        record = self.task_runner.start(
            self.descriptor.name,
            args,
            executor,
            authorization_context_hash=context.authorization_context_hash,
            metadata={"repo_path_hash": repo_id_before},
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


def default_tool_handlers(
    task_runner: TaskRunner, notifications: NotificationManager
) -> list[ToolHandler]:
    return [
        RegisterRepoTool(notifications),
        GraphBuildTaskTool(
            update=False, task_runner=task_runner, notifications=notifications
        ),
        GraphBuildTaskTool(
            update=True, task_runner=task_runner, notifications=notifications
        ),
        RunStaticAnalysisTool(task_runner, notifications),
        RunEvalSuiteTool(task_runner, notifications),
        ComputeRdsFeaturesTool(),
        RecordEvalResultTool(notifications),
        TraceCrossLanguageTool(),
        InterfacePluginReloadTool(notifications, task_runner),
        ClassifyRepoQuestionTool(),
        AnswerRepoQuestionTool(),
        GetInterfaceContractTool(),
        GetRelevantFilesTool(),
        GraphSliceTool(),
        CallGraphTool(callees=False),
        CallGraphTool(callees=True),
        Phase8GitBlameChainTool(),
        RunPatchReviewTool(),
        ClassifyPatchRiskTool(),
        RunIssueResolutionTool(),
        RunImplementationCheckTool(),
        CaptureTraceTool(task_runner),
        RetrieveMemoryTool(),
        RecordTrajectoryTool(),
        MemoryCompactTool(task_runner, notifications),
        PromoteOperationalLessonTool(),
        RunOperationalReviewTool(task_runner),
        RunReadinessAuditTool(task_runner),
        GetPredicateExamplesTool(),
        RunSastRepairTool(),
        EvolveStaticRulesTool(),
    ]


def _repo(context: McpRequestContext, repo_id_or_name: object):
    if not isinstance(repo_id_or_name, str) or not repo_id_or_name:
        raise ToolInvalidArguments("repo is required")
    try:
        return context.workspace.repositories.get_repo(repo_id_or_name)
    except RepositoryNotFoundError as exc:
        raise ToolInvalidArguments(str(exc)) from exc


def _repo_path_for_args(context: McpRequestContext, args: JsonObject) -> Path:
    if args.get("repo_path"):
        return Path(str(args["repo_path"])).expanduser().resolve()
    if args.get("repo_id"):
        return Path(
            context.workspace.repositories.get_repo(str(args["repo_id"])).root_path
        )
    raise ToolInvalidArguments("repo_path or repo_id is required")
