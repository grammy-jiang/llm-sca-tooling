"""Schema and validation tests for task_status / task_result / task_cancel.

Regression coverage for M1: the published tool schemas advertised
`properties: {}` / `required: []` while the handlers required ``task_id``
at runtime, so schema-validating MCP clients could not poll. The fix adds
`task_id` to each descriptor's ``input_schema``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.mcp_server.errors import TaskNotFound, ToolInvalidArguments

_ALL_TIERS = frozenset({1, 2, 3, 4})
_TASK_TOOLS_WITH_TASK_ID = ("task_status", "task_result", "task_cancel")


async def _server(tmp_path: Path) -> MCPServer:
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize()
    return server


@pytest.mark.parametrize("tool_name", _TASK_TOOLS_WITH_TASK_ID)
async def test_task_tool_schema_declares_task_id(
    tmp_path: Path, tool_name: str
) -> None:
    """Each task-handling tool must advertise ``task_id`` as a required arg."""
    server = await _server(tmp_path)
    descriptors = await server.list_tools(tiers=_ALL_TIERS)
    by_name = {d.name: d for d in descriptors}

    assert tool_name in by_name, f"{tool_name} is not registered"
    schema = by_name[tool_name].input_schema

    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    assert "task_id" in schema.get("properties", {})
    assert schema["properties"]["task_id"] == {"type": "string"}
    assert schema.get("required") == ["task_id"]


async def test_task_list_schema_takes_no_args(tmp_path: Path) -> None:
    """task_list intentionally takes no args; do not regress that."""
    server = await _server(tmp_path)
    descriptors = await server.list_tools(tiers=_ALL_TIERS)
    by_name = {d.name: d for d in descriptors}

    assert "task_list" in by_name
    schema = by_name["task_list"].input_schema
    assert schema.get("properties", {}) == {}
    assert schema.get("required", []) == []


@pytest.mark.parametrize("tool_name", _TASK_TOOLS_WITH_TASK_ID)
async def test_task_tool_rejects_missing_task_id(
    tmp_path: Path, tool_name: str
) -> None:
    """Calling without ``task_id`` raises a clear validation error."""
    server = await _server(tmp_path)
    with pytest.raises(ToolInvalidArguments):
        await server.call_tool(tool_name, {})


@pytest.mark.parametrize("tool_name", ("task_status", "task_result"))
async def test_task_tool_rejects_unknown_task_id(
    tmp_path: Path, tool_name: str
) -> None:
    """Calling with a syntactically valid but unknown id raises TaskNotFound."""
    server = await _server(tmp_path)
    with pytest.raises(TaskNotFound):
        await server.call_tool(tool_name, {"task_id": "task:does-not-exist"})
