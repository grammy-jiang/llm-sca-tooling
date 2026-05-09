from __future__ import annotations

from llm_sca_tooling.governance.permissions import PermissionProfileLoader
from llm_sca_tooling.governance.policy import PolicyEvaluator


def test_permission_profile_loader_lists_defaults() -> None:
    loader = PermissionProfileLoader()
    assert "read-only" in loader.list_profiles()
    assert loader.load("scoped-execute").network_allowed is False


def test_policy_evaluator_denies_out_of_scope_edit() -> None:
    evaluator = PolicyEvaluator(path_allowlist=["src/"])
    decision = evaluator.evaluate_tool_call(
        "edit", "edit", "scoped-edit", requested_path="docs/index.md"
    )
    assert decision.action == "deny"


def test_policy_evaluator_requires_approval_for_execute_in_read_only() -> None:
    evaluator = PolicyEvaluator()
    decision = evaluator.evaluate_tool_call("pytest", "execute", "read-only")
    assert decision.action == "approval_required"
