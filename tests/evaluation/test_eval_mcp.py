from __future__ import annotations

import pytest

from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments


def test_eval_tools_run_task_and_resource_round_trip(mcp_server) -> None:
    result = mcp_server.call_tool(
        "run_eval_suite", {"suite": "smoke", "null_mode": True}
    )
    task_id = result.payload["task"]["task_id"]
    payload = mcp_server.task_result(task_id)
    run_id = payload["eval_run_id"]
    assert payload["eval_run"]["instance_count"] == 5
    resource = mcp_server.read_resource(f"code-intelligence://eval/{run_id}")
    assert resource.payload["eval_run"]["eval_run_id"] == run_id
    assert resource.payload["artifact_count"] >= 5
    assert any(
        notification.method == "notifications/resources/updated"
        for notification in mcp_server.drain_notifications()
    )


def test_compute_rds_features_tool_records_artifact(mcp_server) -> None:
    result = mcp_server.call_tool(
        "compute_rds_features", {"instance_id": "file_localisation"}
    )
    assert result.status == "completed"
    assert result.payload["rds_features"]["memorisation_distance"] == 0.5
    assert result.artifact_refs


def test_record_eval_result_requires_harness_condition(mcp_server) -> None:
    payload = mcp_server.task_result(
        mcp_server.call_tool("run_eval_suite", {"suite": "smoke"}).payload["task"][
            "task_id"
        ]
    )
    eval_run = payload["eval_run"]
    eval_run["harness_condition"] = None
    with pytest.raises(ToolInvalidArguments):
        mcp_server.call_tool("record_eval_result", {"eval_run": eval_run})


def test_t3_eval_suite_returns_not_implemented_task(mcp_server) -> None:
    result = mcp_server.call_tool("run_eval_suite", {"suite": "t3"})
    payload = mcp_server.task_result(result.payload["task"]["task_id"])
    assert payload["eval_run"]["status"] == "partial"
    assert "not implemented" in payload["eval_run"]["notes"][0]
