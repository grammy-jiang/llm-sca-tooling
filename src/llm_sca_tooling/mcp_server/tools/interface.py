"""Phase 7 interface plugin MCP tools."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.scanner import FileScanner
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
from llm_sca_tooling.plugins.capability import ConfidenceLevel, TraversalDirection
from llm_sca_tooling.plugins.registry import default_plugin_registry
from llm_sca_tooling.plugins.runner import run_interface_plugins
from llm_sca_tooling.plugins.store import InterfaceIndexStore
from llm_sca_tooling.plugins.traversal import CrossLanguageTraverser
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass
from llm_sca_tooling.schemas.provenance import RepoRef


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
    task_support: str = "none",
    mode: PermissionMode = PermissionMode.SEARCH,
    side_effect: SideEffectClass = SideEffectClass.READ_ONLY,
    notifications: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema={"type": "object"},
        read_only=read_only,
        task_support=task_support,
        permission=ToolPermissionDescriptor(
            required_mode=mode,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=side_effect,
            writes_to_store=not read_only,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
        emits_resource_notifications=notifications,
    )


class TraceCrossLanguageTool(ToolHandler):
    descriptor = _descriptor(
        "trace_cross_language",
        "Trace interface-linked graph hops across language boundaries.",
        _schema(
            {
                "repo": {"type": "string"},
                "symbol": {"type": "string"},
                "direction": {"type": "string"},
                "max_hops": {"type": "integer"},
                "plugins": {"type": "array", "items": {"type": "string"}},
                "min_confidence": {"type": "string"},
                "include_ambiguous": {"type": "boolean"},
                "snapshot": {"type": "string"},
            },
            ["repo", "symbol"],
        ),
        read_only=True,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = _repo(context, args.get("repo"))
        start = _resolve_symbol(context, repo.repo_id, args.get("symbol"))
        if start is None:
            raise ToolInvalidArguments(f"symbol not found: {args.get('symbol')}")
        direction = TraversalDirection(
            str(args.get("direction") or TraversalDirection.BOTH.value)
        )
        min_confidence = ConfidenceLevel(
            str(args.get("min_confidence") or ConfidenceLevel.HEURISTIC.value)
        )
        traverser = CrossLanguageTraverser(
            default_plugin_registry(), context.workspace.graph
        )
        result = traverser.traverse(
            start.node_id,
            direction=direction,
            max_hops=int(args.get("max_hops") or 10),
            plugins=args.get("plugins"),
            min_confidence=min_confidence,
        )
        payload = result.model_dump(mode="json")
        nodes = [
            context.workspace.graph.fetch_node(node_id)
            for node_id in result.reached_node_ids
        ]
        payload.update(
            {
                "start_symbol_path": start.qualified_name
                or start.file_path
                or start.node_id,
                "languages_visited": sorted(
                    {
                        node.properties.get("language")
                        for node in nodes
                        if node and isinstance(node.properties.get("language"), str)
                    }
                ),
                "repos_visited": sorted({node.repo.repo_id for node in nodes if node}),
                "snapshot_ids": {
                    node.repo.repo_id: node.snapshot.worktree_snapshot_id
                    or node.snapshot.git_sha
                    or node.snapshot.captured_ts
                    for node in nodes
                    if node
                },
            }
        )
        if not bool(args.get("include_ambiguous", False)):
            payload["ambiguous_candidates"] = []
        return ToolResult(
            tool_name=self.descriptor.name, status="completed", payload=payload
        )


class PluginReloadTool(ToolHandler):
    descriptor = _descriptor(
        "plugin_reload",
        "Reload interface plugins for registered repositories.",
        _schema(
            {
                "plugin_id": {"type": "string"},
                "repo_ids": {"type": "array", "items": {"type": "string"}},
                "task": {"type": "boolean"},
            }
        ),
        read_only=False,
        task_support="optional",
        mode=PermissionMode.EXECUTE,
        side_effect=SideEffectClass.EXECUTES_CODE,
        notifications=True,
    )

    def __init__(
        self, notifications: NotificationManager, task_runner: TaskRunner | None = None
    ) -> None:
        self.notifications = notifications
        self.task_runner = task_runner

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        if args.get("task") and self.task_runner is not None:
            record = self.task_runner.start(
                self.descriptor.name, args, lambda _record: self._reload(context, args)
            )
            return ToolResult(
                tool_name=self.descriptor.name,
                status="task_created",
                payload={"task": record.model_dump(mode="json")},
                artifact_refs=(
                    [record.result_artifact_ref] if record.result_artifact_ref else []
                ),
            )
        payload = self._reload(context, args)
        notifications = payload.pop("notifications", [])
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=payload,
            notifications=notifications,
        )

    def _reload(self, context: McpRequestContext, args: JsonObject) -> JsonObject:
        plugin_ids = [str(args["plugin_id"])] if args.get("plugin_id") else None
        repo_ids = (
            [str(item) for item in args.get("repo_ids", [])]
            if args.get("repo_ids")
            else [
                repo.repo_id
                for repo in context.workspace.repositories.list_repos(active_only=True)
            ]
        )
        registry = default_plugin_registry()
        aggregate = {
            "plugins_reloaded": [],
            "repos_reloaded": [],
            "interface_records_updated": 0,
            "nodes_added": 0,
            "edges_added": 0,
            "nodes_removed": 0,
            "diagnostics": [],
            "notifications_emitted": [],
            "run_event_ids": [],
        }
        for repo_id in repo_ids:
            repo_row = context.workspace.repositories.get_repo(repo_id)
            latest = context.workspace.snapshots.get_latest_snapshot(repo_row.repo_id)
            if latest is None:
                aggregate["diagnostics"].append(
                    {"code": "snapshot_missing", "repo_id": repo_row.repo_id}
                )
                continue
            repo = RepoRef(
                repo_id=repo_row.repo_id,
                name=repo_row.name,
                root_ref=repo_row.root_path_hash,
                remote_url_hash=repo_row.remote_url_hash,
                default_branch=repo_row.default_branch,
            )
            scanner = FileScanner(IndexingConfig())
            files = scanner.scan(Path(repo_row.root_path), repo, latest.snapshot).files
            summary = run_interface_plugins(
                context.workspace,
                Path(repo_row.root_path),
                repo,
                latest.snapshot,
                files,
                registry=registry,
                plugin_ids=plugin_ids,
            )
            aggregate["plugins_reloaded"].extend(summary.plugins_run)
            aggregate["repos_reloaded"].append(repo_row.repo_id)
            aggregate["interface_records_updated"] += summary.interface_records
            aggregate["nodes_added"] += summary.nodes_added
            aggregate["edges_added"] += summary.edges_added
            aggregate["diagnostics"].extend(
                [
                    diagnostic.model_dump(mode="json")
                    for diagnostic in summary.diagnostics
                ]
            )
        store = InterfaceIndexStore(context.workspace)
        uris = ["code-intelligence://interfaces"]
        for record in store.list_records(
            plugin_id=plugin_ids[0] if plugin_ids and len(plugin_ids) == 1 else None
        ):
            uris.append(
                f"code-intelligence://interfaces/{record.plugin_id}/{record.interface_name}"
            )
        notifications = [
            self.notifications.resources_list_changed({"resource": "interfaces"}),
            *self.notifications.resources_updated(
                *uris, payload={"plugins": aggregate["plugins_reloaded"]}
            ),
        ]
        aggregate["notifications_emitted"] = [
            notification.method for notification in notifications
        ]
        aggregate["plugins_reloaded"] = sorted(set(aggregate["plugins_reloaded"]))
        aggregate["repos_reloaded"] = sorted(set(aggregate["repos_reloaded"]))
        aggregate["notifications"] = [
            notification.model_dump(mode="json") for notification in notifications
        ]
        return aggregate


def _repo(context: McpRequestContext, repo_id_or_name: object):
    if not isinstance(repo_id_or_name, str) or not repo_id_or_name:
        raise ToolInvalidArguments("repo is required")
    return context.workspace.repositories.get_repo(repo_id_or_name)


def _resolve_symbol(context: McpRequestContext, repo_id: str, symbol: object):
    if not isinstance(symbol, str) or not symbol:
        raise ToolInvalidArguments("symbol is required")
    direct = context.workspace.graph.fetch_node(symbol)
    if direct:
        return direct
    nodes = context.workspace.graph.find_symbols(repo_id, qualified_name=symbol)
    if nodes:
        return nodes[0]
    rows = context.workspace.conn.execute(
        "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND (qualified_name=? OR label=? OR file_path=?)",
        (repo_id, symbol, symbol, symbol),
    ).fetchall()
    if rows:
        from llm_sca_tooling.schemas.graph import GraphNode

        return GraphNode.model_validate_json(rows[0]["payload_json"])
    return None
