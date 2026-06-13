"""llm_mode parity across MCP workflow tools (queue item 1).

Every LLM-capable tool accepts llm_mode, fails soft to its null adapter
without a provider, and reports llm_mode_active so degraded runs are
distinguishable from LLM-graded ones.
"""

from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig


async def _server(tmp_path: Path) -> MCPServer:
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize(client_capabilities={})
    return server


def _fake_factory(payload: dict):
    def factory(*args, **kwargs):
        return lambda prompt: json.dumps(payload)

    return factory


async def test_answer_repo_question_llm_mode_fails_soft(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server = await _server(tmp_path)
    result = await server.call_tool(
        "answer_repo_question",
        {"question": "where is validate defined", "llm_mode": True},
    )
    assert result.status == "completed"
    assert result.payload["llm_mode_active"] is False


async def test_answer_repo_question_llm_mode_active_with_fake_provider(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "llm_sca_tooling.llm.get_completion_callable",
        _fake_factory({"answer_text": "validate lives in user_service.py"}),
    )
    server = await _server(tmp_path)
    result = await server.call_tool(
        "answer_repo_question",
        {"question": "where is validate defined", "llm_mode": True},
    )
    assert result.status == "completed"
    assert result.payload["llm_mode_active"] is True


async def test_capture_trace_llm_mode_fails_soft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server = await _server(tmp_path)
    result = await server.call_tool(
        "capture_trace",
        {"script": "print('hi')", "llm_mode": True},
    )
    assert result.status == "completed"
    assert result.payload["llm_mode_active"] is False


async def test_issue_resolution_llm_mode_fails_soft(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server = await _server(tmp_path)
    result = await server.call_tool(
        "run_issue_resolution",
        {"issue_text": "NullPointerException in UserService", "llm_mode": True},
    )
    assert result.status == "completed"
    # Null patch generator fallback: workflow completes normally.
    assert result.payload["report"]["final_verdict"]
