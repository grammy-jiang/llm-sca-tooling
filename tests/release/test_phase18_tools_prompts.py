from __future__ import annotations

import pytest

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


@pytest.fixture
def mcp_server(tmp_path):
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    yield server
    server.shutdown()


def test_operational_review_and_readiness_tools_task_lifecycle(mcp_server) -> None:
    operational = mcp_server.call_tool(
        "run_operational_review", {"run_id": "run:1", "task": True}
    )
    assert operational.status == "task_created"
    op_task_id = operational.payload["task"]["task_id"]
    assert mcp_server.task_result(op_task_id)["report"][
        "process_compliance_verdict"
    ] in {
        "process-compliant",
        "process-noncompliant",
        "trace-incomplete",
        "budget-exhausted",
        "needs-readiness-work",
    }
    readiness = mcp_server.call_tool(
        "run_readiness_audit", {"repo": "repo:demo", "task": True}
    )
    assert readiness.status == "task_created"
    readiness_task_id = readiness.payload["task"]["task_id"]
    assert mcp_server.task_result(readiness_task_id)["report"]["harness_stage"] == "S3"


def test_operational_and_readiness_prompts_are_graduated(mcp_server) -> None:
    operational = mcp_server.get_prompt("operational-review")
    assert operational.workflow_available is True
    assert "run_operational_review" in operational.suggested_tools
    assert "process-compliant" in operational.instructions
    readiness = mcp_server.get_prompt("readiness-audit")
    assert readiness.workflow_available is True
    assert "run_readiness_audit" in readiness.suggested_tools
    assert "S3" in readiness.instructions
