from __future__ import annotations

from llm_sca_tooling.mcp_server.task_store import TaskProgress


def test_tool_descriptors_include_permission_metadata(mcp_server) -> None:
    descriptors = mcp_server.list_tools()
    assert [descriptor.name for descriptor in descriptors] == sorted(
        descriptor.name for descriptor in descriptors
    )
    for descriptor in descriptors:
        assert descriptor.permission.network_requirement == "none"
        assert descriptor.permission.approval_requirement


def test_register_repo_emits_list_changed(mcp_server, mcp_repo) -> None:
    result = mcp_server.call_tool("register_repo", {"repo_path": str(mcp_repo)})
    assert result.status == "completed"
    assert any(
        notification["method"] == "notifications/resources/list_changed"
        for notification in result.notifications
    )


def test_graph_build_task_poll_result_and_notifications(mcp_server, mcp_repo) -> None:
    result = mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)})
    task_id = result.payload["task"]["task_id"]
    assert task_id.startswith("task:")
    assert len(task_id) > 35
    status = mcp_server.task_status(task_id)
    assert status.status == "completed"
    payload = mcp_server.task_result(task_id)
    assert payload["run_id"]
    assert payload["resource_updates"]
    assert any(
        notification.method == "notifications/resources/updated"
        for notification in mcp_server.drain_notifications()
    )


def test_graph_update_task_and_call_graph_tools(mcp_server, mcp_repo) -> None:
    build_payload = mcp_server.task_result(
        mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload[
            "task"
        ]["task_id"]
    )
    (mcp_repo / "src" / "pkg" / "core.py").write_text(
        "def callee(x):\n    return x + 2\n\ndef caller(x):\n    return callee(x)\n",
        encoding="utf-8",
    )
    update_payload = mcp_server.task_result(
        mcp_server.call_tool(
            "graph_update", {"repo_id": build_payload["repo_id"]}
        ).payload["task"]["task_id"]
    )
    assert update_payload["changed_files"] == ["src/pkg/core.py"]
    callers = mcp_server.call_tool(
        "find_callers", {"repo": build_payload["repo_id"], "symbol": "pkg.core:callee"}
    ).payload
    callees = mcp_server.call_tool(
        "find_callees", {"repo": build_payload["repo_id"], "symbol": "pkg.core:caller"}
    ).payload
    assert callers["matches"]
    assert callees["matches"]


def test_task_cancellation_restart_recovery_and_listing_policy(mcp_server) -> None:
    record = mcp_server.tasks.store.create("graph_build", {"repo_path": "/tmp/nope"})
    cancelled = mcp_server.cancel_task(record.task_id)
    assert cancelled.status == "cancelled"
    running = mcp_server.tasks.store.create("graph_build", {"repo_path": "/tmp/nope"})
    running.status = "running"
    running.progress.append(TaskProgress(stage="test", message="running"))
    mcp_server.tasks.store.save(running)
    assert mcp_server.tasks.recover_inflight() == 1
    assert mcp_server.task_status(running.task_id).status == "failed"


def test_plugin_reload_runs_phase7_plugins(mcp_server, mcp_repo) -> None:
    build_payload = mcp_server.task_result(
        mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload[
            "task"
        ]["task_id"]
    )
    result = mcp_server.call_tool(
        "plugin_reload",
        {"plugin_id": "http-rest", "repo_ids": [build_payload["repo_id"]]},
    )
    assert result.status == "completed"
    assert result.payload["plugins_reloaded"] == ["http-rest"]
    assert any(
        notification["method"] == "notifications/resources/list_changed"
        for notification in result.notifications
    )
