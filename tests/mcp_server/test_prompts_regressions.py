from __future__ import annotations


def test_prompt_registry_returns_stubs_without_workflow_execution(mcp_server) -> None:
    names = {prompt.name for prompt in mcp_server.list_prompts()}
    assert names == {"implementation-check", "bug-resolve", "patch-review", "operational-review", "readiness-audit"}
    prompt = mcp_server.get_prompt("patch-review")
    assert not prompt.workflow_available
    assert "not implemented in Phase 4" in prompt.instructions
    assert prompt.sampling.status in {"unknown", "supported", "unsupported"}
    assert "future:run_patch_review" in prompt.suggested_tools


def test_resource_and_tool_descriptor_regression_shape(mcp_server) -> None:
    resource_templates = [resource.uri_template for resource in mcp_server.list_resources()]
    assert resource_templates == [
        "code-intelligence://repos",
        "code-intelligence://schema/{schema_file}",
        "code-intelligence://graph/slice/{repo}/{files}",
        "code-intelligence://graph/{repo}",
        "code-intelligence://summary/{repo}/{symbol_path}",
        "code-intelligence://blame/{repo}/{file_path}",
        "code-intelligence://build-evidence/{repo}",
        "code-intelligence://sarif/{repo}",
        "code-intelligence://sarif/{repo}/{run_id}",
    ]
    tool_permissions = {tool.name: tool.permission.model_dump(mode="json") for tool in mcp_server.list_tools()}
    assert tool_permissions["graph_build"]["writes_to_store"]
    assert tool_permissions["run_static_analysis"]["writes_to_store"]
    assert not tool_permissions["get_graph_slice"]["writes_to_repo"]
