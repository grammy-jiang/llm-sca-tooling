from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sarif.adapters.codeql import CodeQLAdapter


def test_run_static_analysis_external_import_resource_and_notification(
    mcp_server, mcp_repo
) -> None:
    build = mcp_server.task_result(
        mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload[
            "task"
        ]["task_id"]
    )
    fixture = (
        Path(__file__).parents[1]
        / "sarif"
        / "fixtures"
        / "sarif_runs"
        / "external_generic.sarif.json"
    )
    result = mcp_server.call_tool(
        "run_static_analysis",
        {
            "repo": build["repo_id"],
            "analyser": "external",
            "import_sarif_path": str(fixture),
        },
    )
    assert result.status == "completed"
    assert result.payload["alert_count"] == 1
    assert result.payload["bound_alert_count"] == 1
    assert result.payload["warned_by_edge_count"] >= 1
    resource = mcp_server.read_resource(result.payload["sarif_resource_uri"]).payload
    assert resource["severity_summary"]["critical"] == 1
    assert "src/pkg/core.py" in resource["alerts_by_file"]
    listing = mcp_server.read_resource(
        f"code-intelligence://sarif/{build['repo_id']}"
    ).payload
    assert listing["runs"][0]["run_id"] == result.payload["run_id"]
    assert any(
        notification.method == "notifications/resources/updated"
        and notification.uri == result.payload["sarif_resource_uri"]
        for notification in mcp_server.drain_notifications()
    )


def test_run_static_analysis_task_and_delta(mcp_server, mcp_repo) -> None:
    build = mcp_server.task_result(
        mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload[
            "task"
        ]["task_id"]
    )
    fixtures = Path(__file__).parents[1] / "sarif" / "fixtures" / "sarif_runs"
    first = mcp_server.call_tool(
        "run_static_analysis",
        {
            "repo": build["repo_id"],
            "analyser": "external",
            "import_sarif_path": str(fixtures / "delta_before.sarif.json"),
            "task": True,
        },
    )
    first_payload = mcp_server.task_result(first.payload["task"]["task_id"])
    assert first_payload["status"] == "completed"
    second = mcp_server.call_tool(
        "run_static_analysis",
        {
            "repo": build["repo_id"],
            "analyser": "external",
            "import_sarif_path": str(fixtures / "delta_after.sarif.json"),
        },
    )
    assert second.payload["delta_id"]
    assert second.payload["new_critical_high_count"] == 1


def test_run_static_analysis_unregistered_and_unavailable(mcp_server) -> None:
    try:
        mcp_server.call_tool(
            "run_static_analysis",
            {
                "repo": "missing",
                "analyser": "external",
                "import_sarif_path": "/tmp/nope",
            },
        )
    except Exception as exc:
        assert "repository not found" in str(exc)
    else:
        raise AssertionError("unregistered repo was accepted")

    assert CodeQLAdapter().check_availability().available is False
