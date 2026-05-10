from __future__ import annotations

from llm_sca_tooling.fl.localisation import LocalisationRequest, LocalisationService
from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


def test_localisation_service_returns_ranked_files_with_context(
    fl_workspace, fl_repo
) -> None:
    result = LocalisationService(fl_workspace).get_relevant_files(
        LocalisationRequest(
            issue_text=(
                "Traceback (most recent call last):\n"
                '  File "/tmp/repo/src/pkg/core.py", line 3, in validate\n'
                "KeyError: 'name'"
            ),
            repos=[fl_repo.repo_id],
            include_symbols=True,
        )
    )

    assert result.ranked_files[0].file_path == "src/pkg/core.py"
    assert result.ranked_files[0].signals
    assert result.context_bundle is not None
    assert result.context_bundle.files[0].exact_spans
    assert result.ranked_symbols
    assert result.ranked_symbols[0].reasoning_chain
    assert "Embedding retrieval unavailable" in (result.uncertainty or "")


def test_get_relevant_files_tool_returns_artifact_ref(tmp_path, fl_repo) -> None:
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    try:
        repo = server.workspace.repositories.register_repo(
            fl_repo.root_path, name="demo"
        )
        # Reuse the server workspace by indexing the fixture repository through the
        # existing graph build path so the MCP tool sees real graph nodes.
        build = server.task_result(
            server.call_tool("graph_build", {"repo_id": repo.repo_id}).payload["task"][
                "task_id"
            ]
        )
        result = server.call_tool(
            "get_relevant_files",
            {
                "issue_text": 'File "/tmp/repo/src/pkg/core.py", line 3, in validate\nKeyError: name',
                "repos": [build["repo_id"]],
                "include_symbols": True,
            },
        )

        assert result.status == "completed"
        assert result.payload["ranked_files"]
        assert result.payload["context_bundle_ref"]["artifact_id"].startswith(
            "art:fl-context:"
        )
        assert result.artifact_refs
    finally:
        server.shutdown()
