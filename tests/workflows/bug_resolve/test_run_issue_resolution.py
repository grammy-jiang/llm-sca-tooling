"""Tests for the run_issue_resolution MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tools.issue_resolution import (
    RunIssueResolutionTool,
)


def test_tool_descriptor_name() -> None:
    assert RunIssueResolutionTool.descriptor.name == "run_issue_resolution"


def test_tool_descriptor_required_input() -> None:
    schema = RunIssueResolutionTool.descriptor.input_schema
    assert "issue_text" in schema["required"]


def test_tool_call_basic_null_mode(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    try:
        result = server.call_tool(
            "run_issue_resolution",
            {"issue_text": "NPE in foo", "null_mode": True},
        )
        assert result.status == "completed"
        assert "report" in result.payload
        assert result.payload["report"]["final_verdict"] in {
            "resolved",
            "no_fix_found",
            "resolved_with_risk",
        }
        assert result.artifact_refs
    finally:
        server.shutdown()


def test_tool_missing_issue_text_raises(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    try:
        with pytest.raises(ToolInvalidArguments):
            server.call_tool("run_issue_resolution", {})
    finally:
        server.shutdown()


def test_tool_artifact_stored(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    try:
        result = server.call_tool(
            "run_issue_resolution",
            {"issue_text": "NPE in foo", "null_mode": True},
        )
        assert result.artifact_refs
        ref = result.artifact_refs[0]
        assert ref.artifact_id.startswith("art:bug-resolve-report:")
        assert Path(ref.uri).exists()
    finally:
        server.shutdown()
