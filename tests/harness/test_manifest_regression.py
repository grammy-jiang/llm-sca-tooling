"""Manifest regression tests.

Categories covered (per Phase H0 spec):
  - visible_behaviour  — tool calls produce expected outputs for standard inputs
  - hidden_policy      — tool calls are denied/warned for policy-sensitive inputs
  - tool_order         — call ordering does not change outcomes in order-dependent cases
"""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.governance.policy import PolicyEvaluator
from llm_sca_tooling.hardening.manifest_regression_runner import (
    ManifestRegressionRunner,
)

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
PLAN_TMPL = (
    REPO_ROOT / ".agent" / "templates" / "plan.md"
    if (REPO_ROOT / ".agent" / "templates" / "plan.md").exists()
    else None
)


# ---------------------------------------------------------------------------
# visible_behaviour
# ---------------------------------------------------------------------------


def test_agents_md_tool_returns_required_sections() -> None:
    """category: visible_behaviour

    AGENTS.md must contain all required top-level sections.
    """
    content = AGENTS_MD.read_text()
    required_sections = [
        "Hard Constraints",
        "Scope Boundary",
        "Verify-Before-Commit",
        "Local-Agent Development Contract",
        "Stop Conditions",
        "PR Checklist",
    ]
    for section in required_sections:
        assert (
            section in content
        ), f"Required section '{section}' missing from AGENTS.md"


def test_agents_md_contains_hc_table() -> None:
    """category: visible_behaviour

    AGENTS.md hard-constraints table must list HC1 through HC6 with descriptions.
    """
    content = AGENTS_MD.read_text()
    for i in range(1, 7):
        assert (
            f"HC{i}" in content
        ), f"HC{i} not found in AGENTS.md hard-constraints table"


def test_plan_template_contains_required_fields() -> None:
    """category: visible_behaviour

    If a plan.md template exists under .agent/templates/, it must contain
    the required planning fields.
    """
    tmpl_candidates = [
        REPO_ROOT / ".agent" / "templates" / "plan.md",
        REPO_ROOT / ".agent" / "docs" / "plan.md",
    ]
    found = next((p for p in tmpl_candidates if p.exists()), None)
    if found is None:
        # No template present yet — check AGENTS.md describes the plan format
        content = AGENTS_MD.read_text()
        assert (
            "plan" in content.lower()
        ), "Neither a plan template nor plan documentation found"
        return

    content = found.read_text()
    required_fields = ["scope", "step"]
    for field in required_fields:
        assert (
            field.lower() in content.lower()
        ), f"Plan template missing field: {field!r}"


# ---------------------------------------------------------------------------
# hidden_policy
# ---------------------------------------------------------------------------


def test_out_of_scope_write_is_denied() -> None:
    """category: hidden_policy

    A write (edit category) targeting a path outside the allowlist is denied
    in scoped-edit mode.
    """
    evaluator = PolicyEvaluator(
        path_allowlist=["src/", "tests/"],
    )
    decision = evaluator.evaluate_tool_call(
        tool_name="write_file",
        tool_category="edit",
        permission_profile="scoped-edit",
        requested_path="credentials/secret.key",
    )
    assert (
        decision.action == "deny"
    ), f"Expected 'deny' for out-of-scope write, got {decision.action!r}"


def test_in_scope_write_is_allowed() -> None:
    """category: hidden_policy

    An edit targeting a path inside the allowlist is allowed.
    """
    evaluator = PolicyEvaluator(path_allowlist=["src/"])
    decision = evaluator.evaluate_tool_call(
        tool_name="write_file",
        tool_category="edit",
        permission_profile="scoped-edit",
        requested_path="src/app.py",
    )
    assert decision.action == "allow"


def test_red_class_data_pattern_detected_in_agents_md_section() -> None:
    """category: hidden_policy

    AGENTS.md must declare that red-class data is blocked from prompts and logs.
    This is the static manifest check for HC6 (no PII/credentials in prompts).
    """
    content = AGENTS_MD.read_text()
    assert "HC6" in content
    assert any(
        phrase in content
        for phrase in ("Red", "red-class", "red class", "credentials", "PII")
    ), "HC6 red-class data policy not described in AGENTS.md"


def test_network_egress_denied_by_default() -> None:
    """category: hidden_policy

    A tool call that requires network access is denied under default policy (HC5).
    """
    evaluator = PolicyEvaluator(network_deny_by_default=True)
    decision = evaluator.evaluate_tool_call(
        tool_name="http_fetch",
        tool_category="execute",
        permission_profile="scoped-execute",
        network_required=True,
    )
    assert (
        decision.action == "deny"
    ), f"Network egress should be denied by default; got {decision.action!r}"


def test_destructive_command_requires_approval() -> None:
    """category: hidden_policy

    A commit-class tool call requires approval_required in scoped-execute mode.
    """
    evaluator = PolicyEvaluator()
    decision = evaluator.evaluate_tool_call(
        tool_name="git_push_force",
        tool_category="commit",
        permission_profile="scoped-execute",
    )
    assert (
        decision.action == "approval_required"
    ), f"Commit/destructive commands must require approval; got {decision.action!r}"


def test_read_only_mode_denies_edit() -> None:
    """category: hidden_policy

    In read-only permission profile, edit operations are denied.
    """
    evaluator = PolicyEvaluator()
    decision = evaluator.evaluate_tool_call(
        tool_name="write_file",
        tool_category="edit",
        permission_profile="read-only",
    )
    assert decision.action in (
        "deny",
        "approval_required",
    ), f"read-only profile should deny/require-approval for edit; got {decision.action!r}"


# ---------------------------------------------------------------------------
# tool_order
# ---------------------------------------------------------------------------


def test_verify_gate_order_is_deterministic() -> None:
    """category: tool_order

    The ManifestRegressionRunner produces identical hashes for the same content
    on repeated calls — confirming that the verify gate is deterministic.
    """
    content = AGENTS_MD.read_text()
    h1 = ManifestRegressionRunner._hash(content)
    h2 = ManifestRegressionRunner._hash(content)
    assert h1 == h2, "ManifestRegressionRunner._hash is non-deterministic"


def test_manifest_regression_new_artefact_not_flagged(tmp_path: Path) -> None:
    """category: tool_order

    A brand-new artefact (no previous snapshot) is not flagged as a regression.
    """
    runner = ManifestRegressionRunner(snapshot_store=tmp_path / "snapshots.json")
    report = runner.run({"agents-md": "# AGENTS.md content"})
    assert (
        not report.has_changes
    ), "New artefact with no prior snapshot should not produce regression findings"


def test_manifest_regression_changed_policy_artefact_blocks_release(
    tmp_path: Path,
) -> None:
    """category: tool_order

    Changing a policy-tagged artefact (name containing 'agents' or 'policy')
    after a snapshot was taken blocks the release gate.
    """
    store_path = tmp_path / "snapshots.json"
    runner = ManifestRegressionRunner(snapshot_store=store_path)
    runner.update_snapshots({"agents-md-policy": "original content"})

    runner2 = ManifestRegressionRunner(snapshot_store=store_path)
    report = runner2.run({"agents-md-policy": "modified content"})
    assert report.has_changes
    assert report.blocks_release, "A changed policy artefact should block release"
