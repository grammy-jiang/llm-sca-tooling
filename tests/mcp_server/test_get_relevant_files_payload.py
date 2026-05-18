"""Payload-shape tests for ``get_relevant_files``.

Regression coverage for M2: the handler unconditionally inlined the full
``context_bundle`` into the response payload, producing 0.4-1.3 MB JSON
objects that broke token budgets for MCP clients (Claude Code, Anthropic
SDK). The fix gates the inline copy behind ``include_context_bundle``
(default ``False``); ``context_bundle_ref`` is always returned so callers
can fetch the bundle on demand.
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


async def test_default_payload_omits_context_bundle(tmp_path: Path) -> None:
    """By default the payload returns the ranked files without the bundle."""
    server, repo_id = await _server_with_repo(tmp_path)
    try:
        result = await server.call_tool(
            "get_relevant_files",
            {"issue_text": "unknown issue", "repos": [repo_id]},
        )
        payload = result.payload
        assert "context_bundle" not in payload, (
            "Default response must not inline context_bundle "
            "(payload would exceed MCP client token budgets)."
        )
        assert "context_bundle_ref" in payload, (
            "context_bundle_ref must always be returned so callers can "
            "fetch the bundle on demand."
        )
        assert "ranked_files" in payload
    finally:
        await server.close()


async def test_opt_in_payload_includes_context_bundle(tmp_path: Path) -> None:
    """Passing ``include_context_bundle=True`` restores the inline copy."""
    server, repo_id = await _server_with_repo(tmp_path)
    try:
        result = await server.call_tool(
            "get_relevant_files",
            {
                "issue_text": "unknown issue",
                "repos": [repo_id],
                "include_context_bundle": True,
            },
        )
        payload = result.payload
        assert "context_bundle" in payload
        assert isinstance(payload["context_bundle"], dict)
        # ContextBundle.files is a required field on the model
        assert "files" in payload["context_bundle"]
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
