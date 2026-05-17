"""Phase 4 MCP server core tests."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.mcp_server.errors import (
    ResourceInvalidUri,
    ResourceNotFound,
    ResourceTooLarge,
    TaskNotFound,
    ToolInvalidArguments,
    ToolNotFound,
    ToolPermissionDenied,
    ToolUnavailable,
)
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import (
    parse_resource_uri,
    validate_relative_path,
)
from llm_sca_tooling.mcp_server.sampling import detect_sampling
from llm_sca_tooling.mcp_server.serialization import canonical_json
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.telemetry import McpTelemetry
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolResult,
)


def _config(tmp_path: Path, **overrides: object) -> McpServerConfig:
    return McpServerConfig(workspace_path=tmp_path / "workspace", **overrides)


async def _server(tmp_path: Path, **overrides: object) -> MCPServer:
    server = MCPServer(_config(tmp_path, **overrides))
    await server.initialize(client_capabilities={"sampling": {"maxTokens": 1000}})
    return server


async def _wait_task(server: MCPServer, task_id: str) -> dict:
    for _ in range(100):
        status = await server.call_tool("task_status", {"task_id": task_id})
        task = status.payload["task"]
        if task["status"] in {"completed", "failed", "cancelled"}:
            return task
        await asyncio.sleep(0.01)
    raise AssertionError(f"task {task_id} did not finish")


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (repo / "src" / "app.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n"
    )
    (repo / "src" / "other.py").write_text("from .app import main\n")
    return repo


async def test_server_capabilities_resources_tools_and_prompts(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    try:
        capabilities = await server.capabilities()
        # MCP 2025-11-25: resources/tools/prompts/tasks are objects, not booleans.
        assert capabilities["resources"] == {"subscribe": True, "listChanged": True}
        assert capabilities["tools"] == {"listChanged": True}
        assert capabilities["prompts"] == {"listChanged": False}
        # tasks is a first-class ServerCapabilities field in 2025-11-25.
        assert isinstance(capabilities.get("tasks"), dict)
        # sampling is a client capability; must NOT appear in server capabilities.
        assert "sampling" not in capabilities
        resources = await server.list_resources()
        assert "code-intelligence://repos" in [r.uri_template for r in resources]
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert tool_names[:4] == [
            "register_repo",
            "graph_build",
            "graph_update",
            "plugin_reload",
        ]
        assert all(t.permissions.network_requirement == "none" for t in tools)
        prompts = await server.list_prompts()
        prompt_names = {p["name"] for p in prompts}
        assert {
            "implementation-check",
            "bug-resolve",
            "patch-review",
            "operational-review",
            "readiness-audit",
            "evaluate",
            "audit",
            "risk-classify",
            "sast-repair",
        } <= prompt_names
        patch_prompt = await server.get_prompt("patch-review")
        assert "not implemented in Phase 4" in patch_prompt["limitation"]
    finally:
        await server.close()


async def test_resource_uri_validation() -> None:
    parsed = parse_resource_uri("code-intelligence://graph/slice/repo%3A1/src%2Fapp.py")
    assert parsed.segments == ("graph", "slice", "repo:1", "src/app.py")
    assert validate_relative_path("src/app.py") == "src/app.py"
    with pytest.raises(ResourceInvalidUri):
        parse_resource_uri("file://graph/repo")
    with pytest.raises(ResourceInvalidUri):
        parse_resource_uri("code-intelligence:/repos")
    with pytest.raises(ResourceInvalidUri):
        parse_resource_uri("code-intelligence://%2E")
    with pytest.raises(ResourceInvalidUri):
        parse_resource_uri("code-intelligence://graph/repo%5Cbad")
    with pytest.raises(ResourceInvalidUri):
        validate_relative_path("")
    with pytest.raises(ToolInvalidArguments):
        validate_relative_path("../secret.py", for_tool=True)


def test_structured_errors_and_serialization() -> None:
    assert ResourceTooLarge("too large").to_dict()["code"] == "ResourceTooLarge"
    assert ToolUnavailable("unavailable").to_dict()["message"] == "unavailable"
    assert TaskNotFound("missing").to_dict()["details"] == {}
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


async def test_registry_duplicate_and_missing_cases() -> None:
    resources = ResourceRegistry()

    async def handler(uri: str) -> ResourceResult:
        return ResourceResult(uri=uri, media_type="application/json", payload={})

    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://repos",
        name="repos",
        description="repos",
    )
    resources.register(descriptor, handler)
    with pytest.raises(ValueError, match="duplicate resource"):
        resources.register(descriptor, handler)
    with pytest.raises(ResourceNotFound):
        await resources.read("code-intelligence://missing")

    tools = ToolRegistry()

    async def tool_handler(args: dict) -> ToolResult:
        return ToolResult(tool_name="x", status="completed", payload=args)

    tool = ToolDescriptor(
        name="x",
        description="x",
        input_schema={},
        output_schema={},
        read_only=True,
        permissions=ToolPermissionDescriptor(
            required_mode="read/search",
            path_scope="registered repos",
            side_effect_class="none",
        ),
    )
    tools.register(tool, tool_handler)
    with pytest.raises(ValueError, match="duplicate tool"):
        tools.register(tool, tool_handler)
    assert tools.get_descriptor("x").name == "x"
    assert (await tools.call("x", {"ok": True})).payload == {"ok": True}
    with pytest.raises(ToolNotFound):
        tools.get_descriptor("missing")
    with pytest.raises(ToolNotFound):
        await tools.call("missing", {})


async def test_register_repo_resource_and_notifications(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    repo = _make_repo(tmp_path)
    try:
        result = await server.call_tool("register_repo", {"repo_path": str(repo)})
        assert result.status == "completed"
        assert result.payload["repo"]["name"] == "repo"
        notes = server.drain_notifications()
        assert notes[0]["method"] == "notifications/resources/list_changed"
        repos = await server.read_resource("code-intelligence://repos")
        assert repos.payload["repos"][0]["root_path_hash"]
        assert "root_path" not in repos.payload["repos"][0]
        build_evidence = await server.read_resource(
            f"code-intelligence://build-evidence/{result.payload['repo']['repo_id']}"
        )
        assert build_evidence.payload["has_evidence"] is False
        with pytest.raises(ResourceNotFound):
            await server.read_resource(
                f"code-intelligence://graph/{result.payload['repo']['repo_id']}"
            )
        assert server.telemetry_events()[0]["redaction_status"] == "not_required"
    finally:
        await server.close()


async def test_run_readiness_audit_persists_readiness_resource(
    tmp_path: Path,
) -> None:
    server = await _server(tmp_path)
    repo = _make_repo(tmp_path)
    try:
        registered = await server.call_tool("register_repo", {"repo_path": str(repo)})
        repo_id = registered.payload["repo"]["repo_id"]

        result = await server.call_tool("run_readiness_audit", {"repo": repo_id})

        assert result.status == "completed"
        resource = await server.read_resource(
            f"code-intelligence://readiness/{repo_id}"
        )
        assert resource.payload["repo_id"] == repo_id
        assert resource.payload["stage"] == result.payload["report"]["harness_stage"]
        assert (
            resource.payload["total_score"]
            == result.payload["report"]["ai_readiness_score"]
        )
        assert (
            resource.payload["payload"]["report_id"]
            == result.payload["report"]["report_id"]
        )
    finally:
        await server.close()


async def test_graph_build_task_resources_and_graph_tools(tmp_path: Path) -> None:
    server = await _server(tmp_path, enable_task_list=True)
    repo = _make_repo(tmp_path)
    try:
        build = await server.call_tool("graph_build", {"repo_path": str(repo)})
        task = build.payload["task"]
        assert re.match(r"task:[A-Za-z0-9_-]{32,}", task["task_id"])
        pending_result = await server.call_tool(
            "task_result", {"task_id": task["task_id"]}
        )
        assert pending_result.payload["result_available"] is False
        final = await _wait_task(server, task["task_id"])
        assert final["status"] == "completed"
        repo_id = final["result"]["repo_id"]

        schemas = [
            await server.read_resource("code-intelligence://schema/graph.schema.json"),
            await server.read_resource(
                "code-intelligence://schema/run-record.schema.json"
            ),
        ]
        assert all(s.media_type == "application/schema+json" for s in schemas)
        graph = await server.read_resource(f"code-intelligence://graph/{repo_id}")
        assert graph.payload["node_count"] > 0
        assert graph.payload["edge_type_counts"]["calls"] >= 1
        graph_slice = await server.read_resource(
            f"code-intelligence://graph/slice/{repo_id}/src%2Fapp.py"
        )
        assert graph_slice.payload["requested_files"] == ["src/app.py"]
        multi_slice = await server.read_resource(
            f"code-intelligence://graph/slice/{repo_id}/src%2Fapp.py,src%2Fother.py"
        )
        assert multi_slice.payload["snapshot_consistency"] == "clean"
        tool_slice = await server.call_tool(
            "get_graph_slice", {"repo": repo_id, "files": ["src/app.py"]}
        )
        assert tool_slice.payload["nodes"]
        empty_slice = await server.call_tool(
            "get_graph_slice", {"repo": repo_id, "files": []}
        )
        assert empty_slice.payload["snapshot_consistency"] == "unknown"
        build_evidence = await server.read_resource(
            f"code-intelligence://build-evidence/{repo_id}"
        )
        assert "pyproject.toml" in build_evidence.payload["package_manager_files"]
        callees = await server.call_tool(
            "find_callees", {"repo": repo_id, "symbol": "main"}
        )
        assert callees.payload["edges"]
        callers = await server.call_tool(
            "find_callers", {"repo": repo_id, "symbol": "helper"}
        )
        assert callers.payload["edges"]
        missing_symbol = await server.call_tool(
            "find_callers",
            {"repo": repo_id, "symbol": "missing", "include_cross_repo": True},
        )
        assert {d["code"] for d in missing_symbol.diagnostics} == {
            "CROSS_REPO_UNAVAILABLE",
            "SYMBOL_NOT_FOUND",
        }
        summary = await server.read_resource(
            f"code-intelligence://summary/{repo_id}/main"
        )
        assert summary.payload["status"] == "cache_miss"
        artifact_path = repo / ".llm-sca" / "blame.json"
        artifact_path.parent.mkdir(exist_ok=True)
        artifact_path.write_text("{}")
        await server._require_context().workspace.artifacts.record_artifact(
            "artifact:blame",
            "blame",
            artifact_path.as_uri() + "#src/app.py",
            "not_required",
            repo_id=repo_id,
        )
        blame_resource = await server.read_resource(
            f"code-intelligence://blame/{repo_id}/src%2Fapp.py"
        )
        assert blame_resource.payload["status"] == "available"
        blame = await server.call_tool(
            "git_blame_chain", {"repo": repo_id, "file": "src/app.py"}
        )
        assert blame.payload["artifact_refs"]
        plugin = await server.call_tool("plugin_reload", {"plugin_id": "x"})
        assert plugin.status == "unavailable"
        tasks = await server.call_tool("task_list", {})
        assert tasks.payload["tasks"]
        update = await server.call_tool("graph_update", {"repo_id": repo_id})
        assert (await _wait_task(server, update.payload["task"]["task_id"]))[
            "status"
        ] in {
            "completed",
            "failed",
        }
        assert any(
            n["method"] == "notifications/resources/updated"
            for n in server.drain_notifications()
        )
    finally:
        await server.close()


async def test_task_cancel_list_policy_and_restart_recovery(tmp_path: Path) -> None:
    telemetry = McpTelemetry()
    manager = TaskManager(tmp_path, _config(tmp_path), telemetry)
    task = manager.create_task("graph_build", {"repo_path": "x"})
    cancelled = manager.cancel(task.task_id)
    assert cancelled.status == "cancelled"
    with pytest.raises(ToolPermissionDenied):
        manager.list_tasks()

    listing_manager = TaskManager(
        tmp_path, _config(tmp_path, enable_task_list=True), telemetry
    )
    queued = listing_manager.create_task("graph_build", {"repo_path": "x"})
    recovered = TaskManager(
        tmp_path, _config(tmp_path, enable_task_list=True), telemetry
    )
    assert recovered.get(queued.task_id).status == "failed"
    assert recovered.list_tasks()

    async def failing_runner(task) -> dict:
        raise RuntimeError("boom")

    failed = recovered.submit("graph_build", {"repo_path": "x"}, failing_runner)
    await asyncio.sleep(0.05)
    assert recovered.get(failed.task_id).status == "failed"

    async def slow_runner(task) -> dict:
        await asyncio.sleep(0.05)
        return {"ok": True}

    running = recovered.submit("graph_build", {"repo_path": "x"}, slow_runner)
    await asyncio.sleep(0.01)
    assert recovered.cancel(running.task_id).status == "cancelling"
    await asyncio.sleep(0.06)
    assert recovered.result(running.task_id)["result_available"] is False

    completed = recovered.create_task("graph_build", {"repo_path": "x"})
    completed.status = "completed"
    completed.result = {"ok": True}
    assert recovered.result(completed.task_id)["result"] == {"ok": True}

    expired = recovered.create_task("graph_build", {"repo_path": "x"})
    expired.expires_ts = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert recovered.get(expired.task_id).status == "expired"
    with pytest.raises(TaskNotFound):
        recovered.get("task:missing")
    owned = recovered.create_task(
        "graph_build", {"repo_path": "x"}, authorization_context_hash="owner"
    )
    with pytest.raises(ToolPermissionDenied):
        recovered.get(owned.task_id, authorization_context_hash="other")


async def test_sampling_notifications_and_prompt_errors(tmp_path: Path) -> None:
    assert detect_sampling(None).status == "unknown"
    assert detect_sampling({"sampling": False}).status == "unsupported"
    notifications = NotificationManager()
    notifications.subscribe("code-intelligence://repos")
    notifications.emit_updated("code-intelligence://repos", {"changed": True})
    assert notifications.peek()[0]["payload"] == {"changed": True}
    notifications.unsubscribe("code-intelligence://repos")
    assert notifications.list_subscriptions() == []

    server = await _server(tmp_path)
    try:
        await server.subscribe("code-intelligence://repos")
        server._require_subscriptions().unsubscribe("code-intelligence://repos")
        with pytest.raises(ResourceNotFound):
            await server.subscribe("code-intelligence://missing")
        with pytest.raises(ResourceNotFound):
            await server.get_prompt("missing")
        with pytest.raises(RuntimeError):
            MCPServer().drain_notifications()
    finally:
        await server.close()


async def test_tool_refusals_and_resource_invalid_shapes(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    repo = _make_repo(tmp_path)
    try:
        with pytest.raises(ToolInvalidArguments):
            await server.call_tool("register_repo", {})
        with pytest.raises(ToolInvalidArguments):
            await server.call_tool(
                "register_repo", {"repo_path": str(repo / "missing")}
            )
        registered = await server.call_tool("register_repo", {"repo_path": str(repo)})
        repo_id = registered.payload["repo"]["repo_id"]
        with pytest.raises(ToolInvalidArguments):
            await server.call_tool("get_graph_slice", {"repo": repo_id, "files": "bad"})
        with pytest.raises(ToolInvalidArguments):
            await server.call_tool("find_callers", {"repo": repo_id})
        with pytest.raises(ResourceNotFound):
            await server.read_resource("code-intelligence://repos/extra")
        with pytest.raises(ResourceInvalidUri):
            await server.read_resource("code-intelligence://graph/slice/repo")
        with pytest.raises(ResourceInvalidUri):
            await server.read_resource("code-intelligence://summary/repo")
        with pytest.raises(ResourceInvalidUri):
            await server.read_resource("code-intelligence://blame/repo")
        with pytest.raises(ResourceInvalidUri):
            await server.read_resource("code-intelligence://build-evidence/repo/extra")
    finally:
        await server.close()
