from __future__ import annotations


def test_prompt_registry_returns_stubs_without_workflow_execution(mcp_server) -> None:
    names = {prompt.name for prompt in mcp_server.list_prompts()}
    assert names == {
        "implementation-check",
        "bug-resolve",
        "patch-review",
        "operational-review",
        "readiness-audit",
    }
    prompt = mcp_server.get_prompt("patch-review")
    assert prompt.workflow_available
    assert "run_patch_review" in prompt.instructions
    assert "four-axis" in prompt.instructions or "Correctness" in prompt.instructions
    assert prompt.sampling.status in {"unknown", "supported", "unsupported"}
    assert "run_patch_review" in prompt.suggested_tools
    assert not any(tool.startswith("future:") for tool in prompt.suggested_tools)


def test_resource_and_tool_descriptor_regression_shape(mcp_server) -> None:
    resource_templates = [
        resource.uri_template for resource in mcp_server.list_resources()
    ]
    assert resource_templates == [
        "code-intelligence://repos",
        "code-intelligence://skills",
        "code-intelligence://skills/{name}",
        "code-intelligence://schema/{schema_file}",
        "code-intelligence://graph/slice/{repo}/{files}",
        "code-intelligence://graph/{repo}",
        "code-intelligence://summary/{repo}/{symbol_path}",
        "code-intelligence://blame/{repo}/{file_path}",
        "code-intelligence://build-evidence/{repo}",
        "code-intelligence://interfaces",
        "code-intelligence://interfaces/{plugin_id}/{interface_name}",
        "code-intelligence://sarif/{repo}",
        "code-intelligence://sarif/{repo}/{run_id}",
        "code-intelligence://eval/{run_id}",
        "code-intelligence://memory/{repo}/trajectories",
        "code-intelligence://runs/{run_id}",
        "code-intelligence://runs/{run_id}/harness-condition",
        "code-intelligence://operations/{repo}/ledger",
        "code-intelligence://governance/{repo}/policy",
        "code-intelligence://governance/{repo}/manifest-state",
        "code-intelligence://readiness/{repo}",
        "code-intelligence://incidents/{incident_id}",
    ]
    tool_permissions = {
        tool.name: tool.permission.model_dump(mode="json")
        for tool in mcp_server.list_tools()
    }
    assert tool_permissions["graph_build"]["writes_to_store"]
    assert tool_permissions["run_static_analysis"]["writes_to_store"]
    assert tool_permissions["plugin_reload"]["writes_to_store"]
    assert not tool_permissions["classify_repo_question"]["writes_to_store"]
    assert not tool_permissions["answer_repo_question"]["writes_to_repo"]
    assert not tool_permissions["get_interface_contract"]["runs_subprocesses"]
    assert not tool_permissions["git_blame_chain"]["runs_subprocesses"]
    assert not tool_permissions["trace_cross_language"]["writes_to_store"]
    assert not tool_permissions["get_graph_slice"]["writes_to_repo"]
    assert tool_permissions["run_eval_suite"]["writes_to_store"]
    assert tool_permissions["compute_rds_features"]["writes_to_store"]
    assert tool_permissions["record_eval_result"]["writes_to_store"]
    assert not tool_permissions["retrieve_memory"]["writes_to_store"]
    assert tool_permissions["record_trajectory"]["writes_to_store"]
    assert tool_permissions["memory_compact"]["writes_to_store"]
    assert tool_permissions["promote_operational_lesson"]["writes_to_store"]
    assert tool_permissions["record_run_event"]["writes_to_store"]
    assert tool_permissions["record_harness_condition"]["writes_to_store"]
    assert tool_permissions["record_incident"]["writes_to_store"]
    assert not tool_permissions["evaluate_tool_policy"]["writes_to_store"]
    assert not tool_permissions["classify_harness_drift"]["writes_to_store"]
    assert not tool_permissions["assess_harness_stage"]["writes_to_store"]
    assert not tool_permissions["compare_run_traces"]["writes_to_store"]
    assert not tool_permissions["detect_run_anomalies"]["writes_to_store"]
    assert not tool_permissions["validate_harness_controls"]["writes_to_store"]
    assert not tool_permissions["compute_readiness_score"]["writes_to_store"]
    assert not tool_permissions["run_prompt_manifest_regression"]["writes_to_store"]
    assert tool_permissions["run_maintainability_oracles"]["runs_subprocesses"]
