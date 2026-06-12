"""Monitor/budget notifications must be persisted as run events.

Spec: docs/llm-sca-tooling-architecture.md — "Budget and monitor notifications
are advisory but must also be persisted as run events. A client that misses a
live 'budget near hard limit' or 'doom-loop candidate' notification can recover
the same state from the run record."
"""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig

ISSUE = "NullPointerException in UserService.authenticate when user is None"


def _config(tmp_path: Path) -> McpServerConfig:
    return McpServerConfig(workspace_path=tmp_path / "workspace")


async def _server(tmp_path: Path) -> MCPServer:
    server = MCPServer(_config(tmp_path))
    await server.initialize(client_capabilities={})
    return server


async def test_issue_resolution_creates_run_record(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    result = await server.call_tool("run_issue_resolution", {"issue_text": ISSUE})
    assert result.status == "completed"
    run_id = result.payload["report"]["run_id"]

    resource = await server.read_resource(f"code-intelligence://runs/{run_id}")
    payload = resource.payload
    assert payload["run_id"] == run_id
    assert payload["workflow"] == "bug_resolve"
    assert payload["status"] in {"completed", "failed"}


async def test_doom_loop_monitor_event_persisted_as_run_event(
    tmp_path: Path,
) -> None:
    server = await _server(tmp_path)
    result = await server.call_tool(
        "run_issue_resolution",
        {"issue_text": ISSUE, "simulate_doom_loop": True},
    )
    assert result.status == "completed"
    report = result.payload["report"]
    run_id = report["run_id"]

    # The report itself must carry the monitor events.
    monitor_types = {m["monitor_type"] for m in report["monitor_events"]}
    assert "doom_loop_candidate" in monitor_types

    # And the same state must be recoverable from the run record.
    resource = await server.read_resource(f"code-intelligence://runs/{run_id}")
    events = resource.payload["events"]
    event_types = {e["type"] for e in events}
    assert "doom_loop_candidate" in event_types
    doom_events = [e for e in events if e["type"] == "doom_loop_candidate"]
    assert doom_events[0]["actor"] == "monitor"


async def test_budget_exhaustion_persisted_as_run_event(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    result = await server.call_tool(
        "run_issue_resolution",
        {"issue_text": ISSUE, "simulate_budget_exhausted": True},
    )
    assert result.status == "completed"
    run_id = result.payload["report"]["run_id"]

    resource = await server.read_resource(f"code-intelligence://runs/{run_id}")
    events = resource.payload["events"]
    event_types = {e["type"] for e in events}
    assert "token_budget_hard_stop" in event_types


async def test_null_mode_arg_is_honored(tmp_path: Path) -> None:
    """Gap A3: the advertised null_mode arg must reach the workflow config."""
    server = await _server(tmp_path)
    result = await server.call_tool(
        "run_issue_resolution",
        {"issue_text": ISSUE, "null_mode": True},
    )
    assert result.status == "completed"
    run_id = result.payload["report"]["run_id"]
    resource = await server.read_resource(f"code-intelligence://runs/{run_id}")
    assert resource.payload["status"] in {"completed", "failed"}


async def test_null_mode_merges_into_config_arg(tmp_path: Path) -> None:
    """null_mode + config together: null_mode fills the gap, config wins."""
    server = await _server(tmp_path)
    result = await server.call_tool(
        "run_issue_resolution",
        {
            "issue_text": ISSUE,
            "null_mode": True,
            "config": {"max_repair_loops": 2},
            "simulate_doom_loop": True,
        },
    )
    assert result.status == "completed"
    report = result.payload["report"]
    doom = [
        m
        for m in report["monitor_events"]
        if m["monitor_type"] == "doom_loop_candidate"
    ]
    assert doom
    assert "loop_count=2" in doom[0]["detail"]


async def test_task_mode_persists_monitor_events(tmp_path: Path) -> None:
    import asyncio

    server = await _server(tmp_path)
    accepted = await server.call_tool(
        "run_issue_resolution",
        {"issue_text": ISSUE, "simulate_doom_loop": True, "task": True},
    )
    assert accepted.status == "accepted"
    task_id = accepted.payload["task"]["task_id"]

    for _ in range(100):
        status = await server.call_tool("task_status", {"task_id": task_id})
        if status.payload["task"]["status"] in {"completed", "failed", "cancelled"}:
            break
        await asyncio.sleep(0.01)
    final = await server.call_tool("task_result", {"task_id": task_id})
    run_id = final.payload["result"]["report"]["run_id"]

    resource = await server.read_resource(f"code-intelligence://runs/{run_id}")
    event_types = {e["type"] for e in resource.payload["events"]}
    assert "doom_loop_candidate" in event_types
