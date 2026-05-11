"""Tests for the policy evaluator."""

from __future__ import annotations

import pytest

from llm_sca_tooling.governance.policy import PolicyEvaluator


@pytest.fixture()
def evaluator() -> PolicyEvaluator:
    return PolicyEvaluator(path_allowlist=["src/", "tests/"])


def test_read_allowed_in_all_profiles(evaluator: PolicyEvaluator) -> None:
    for profile in (
        "read-only",
        "plan",
        "scoped-edit",
        "scoped-execute",
        "review-commit",
    ):
        dec = evaluator.evaluate_tool_call("Read", "read", profile)
        assert dec.action == "allow", f"Expected allow in {profile}"


def test_execute_denied_in_read_only(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call("Bash", "execute", "read-only")
    assert dec.action in ("deny", "approval_required")


def test_execute_approval_required_in_plan(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call("Bash", "execute", "plan")
    assert dec.action in ("deny", "approval_required")


def test_execute_allowed_in_scoped_execute(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call("Bash", "execute", "scoped-execute")
    assert dec.action == "allow"


def test_network_denied_by_default(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call(
        "curl", "execute", "scoped-execute", network_required=True
    )
    assert dec.action == "deny"


def test_path_outside_allowlist_denied(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call(
        "Edit", "edit", "scoped-edit", requested_path="/etc/passwd"
    )
    assert dec.action == "deny"


def test_path_inside_allowlist_allowed(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call(
        "Edit", "edit", "scoped-edit", requested_path="src/foo.py"
    )
    assert dec.action == "allow"


def test_policy_decision_has_reason(evaluator: PolicyEvaluator) -> None:
    dec = evaluator.evaluate_tool_call("Bash", "execute", "read-only")
    assert dec.reason


def test_review_commit_allows_all(evaluator: PolicyEvaluator) -> None:
    for category in ("read", "search", "edit", "execute", "review", "commit"):
        dec = evaluator.evaluate_tool_call("tool", category, "review-commit")
        assert dec.action == "allow", f"Expected allow for {category}"
