"""Payload-shape tests for ``get_relevant_files``.

Regression coverage for M2: the handler unconditionally inlined the full
``context_bundle`` into the response payload, producing 0.4-1.3 MB JSON
objects that broke token budgets for MCP clients (Claude Code, Anthropic
SDK).

Resolution: introduce ``include_context_bundle`` as an opt-out flag.
Default remains ``True`` (inline copy preserved) because the existing
``context_bundle_ref`` is only inline metadata and no real fetchable
resource is registered yet; flipping the default is gated on that
architectural follow-up (plan-06 §3). Callers that face token-budget
limits can pass ``include_context_bundle=False`` to opt out.
"""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig


async def _server_with_repo(tmp_path: Path) -> tuple[MCPServer, str]:
    """Start an MCP server and register the tmp_path as a repo."""
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize()
    registered = await server.call_tool(
        "register_repo",
        {"repo_path": str(tmp_path), "name": "m2-fixture"},
    )
    return server, registered.payload["repo"]["repo_id"]


async def test_default_payload_includes_context_bundle(tmp_path: Path) -> None:
    """Default preserves the inline copy until a fetchable resource exists.

    See plan-06 §3 for the follow-up that will register a real
    ``context-bundle`` resource and let the default flip to ``False``.
    """
    server, repo_id = await _server_with_repo(tmp_path)
    try:
        result = await server.call_tool(
            "get_relevant_files",
            {"issue_text": "unknown issue", "repos": [repo_id]},
        )
        payload = result.payload
        assert "context_bundle" in payload, (
            "Default must inline context_bundle until a fetchable "
            "context-bundle resource is registered."
        )
        assert isinstance(payload["context_bundle"], dict)
        assert "files" in payload["context_bundle"]
        assert "ranked_files" in payload
        assert "context_bundle_ref" in payload
    finally:
        await server.close()


async def test_opt_out_payload_omits_context_bundle(tmp_path: Path) -> None:
    """Passing ``include_context_bundle=False`` drops the inline copy.

    This is the escape hatch for clients that hit token-budget limits
    (audit skill, IDE MCP clients) — they trade losing the bundle for a
    payload small enough to consume.
    """
    server, repo_id = await _server_with_repo(tmp_path)
    try:
        result = await server.call_tool(
            "get_relevant_files",
            {
                "issue_text": "unknown issue",
                "repos": [repo_id],
                "include_context_bundle": False,
            },
        )
        payload = result.payload
        assert "context_bundle" not in payload
        assert "ranked_files" in payload
        assert "context_bundle_ref" in payload
    finally:
        await server.close()


async def test_get_relevant_files_schema_advertises_include_context_bundle(
    tmp_path: Path,
) -> None:
    """The new opt-in flag must appear in the published tool schema."""
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize()
    try:
        descriptors = await server.list_tools(tiers=frozenset({1, 2, 3, 4}))
        by_name = {d.name: d for d in descriptors}
        schema = by_name["get_relevant_files"].input_schema
        assert "include_context_bundle" in schema["properties"]
        assert schema["properties"]["include_context_bundle"] == {"type": "boolean"}
        # Existing required arg should be unchanged.
        assert schema["required"] == ["issue_text"]
    finally:
        await server.close()
