from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tools.impl_check import RunImplementationCheckTool


def test_descriptor_name() -> None:
    assert RunImplementationCheckTool.descriptor.name == "run_implementation_check"


def test_descriptor_required_input() -> None:
    assert "spec" in RunImplementationCheckTool.descriptor.input_schema["required"]


def test_call_basic_null_mode(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "ws")
    ).start()
    try:
        result = server.call_tool(
            "run_implementation_check",
            {"spec": "The `foo` function must work.\n", "null_mode": True},
        )
        assert result.status == "completed"
        assert "report" in result.payload
        assert "clause_verdict_matrix" in result.payload
        assert result.artifact_refs
    finally:
        server.shutdown()


def test_missing_spec_raises(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "ws")
    ).start()
    try:
        with pytest.raises(ToolInvalidArguments):
            server.call_tool("run_implementation_check", {})
    finally:
        server.shutdown()


def test_empty_spec_raises(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "ws")
    ).start()
    try:
        with pytest.raises(ToolInvalidArguments):
            server.call_tool("run_implementation_check", {"spec": "   "})
    finally:
        server.shutdown()


def test_artifact_stored(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "ws")
    ).start()
    try:
        result = server.call_tool(
            "run_implementation_check",
            {"spec": "The system must work.\n"},
        )
        assert result.artifact_refs
        ref = result.artifact_refs[0]
        assert ref.artifact_id.startswith("art:impl-check-report:")
        assert Path(ref.uri).exists()
    finally:
        server.shutdown()


def test_invalid_run_id_raises(tmp_path: Path) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "ws")
    ).start()
    try:
        with pytest.raises(ToolInvalidArguments):
            server.call_tool(
                "run_implementation_check",
                {"spec": "must work.\n", "run_id": 123},
            )
    finally:
        server.shutdown()
