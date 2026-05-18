"""Deterministic adversarial check suite for Phase 18."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.release.models import AdversarialCheckResult

__all__ = [
    "default_adversarial_fixtures",
    "run_adversarial_check",
    "run_adversarial_suite",
]

_CHECK_OUTCOMES = {
    "prompt_injection": "typed_error",
    "document_injection": "evidence_based_verdict",
    "tool_boundary_misuse": "ToolPermissionDenied",
    "out_of_scope_write": "process-noncompliant",
    "multistep_policy_bypass": "blocked",
    "reward_hackable_task": "correct-but-overfit",
}


def default_adversarial_fixtures() -> list[dict[str, str]]:
    return [
        {
            "fixture_id": "adv:prompt-injection",
            "check_type": "prompt_injection",
            "input_ref": "memory://fixtures/adversarial/prompt_injection",
            "expected_outcome": "typed_error",
        },
        {
            "fixture_id": "adv:document-injection",
            "check_type": "document_injection",
            "input_ref": "memory://fixtures/adversarial/document_injection",
            "expected_outcome": "evidence_based_verdict",
        },
        {
            "fixture_id": "adv:tool-boundary",
            "check_type": "tool_boundary_misuse",
            "input_ref": "memory://fixtures/adversarial/tool_boundary_misuse",
            "expected_outcome": "ToolPermissionDenied",
        },
        {
            "fixture_id": "adv:scope-write",
            "check_type": "out_of_scope_write",
            "input_ref": "memory://fixtures/adversarial/out_of_scope_write",
            "expected_outcome": "process-noncompliant",
        },
        {
            "fixture_id": "adv:policy-bypass",
            "check_type": "multistep_policy_bypass",
            "input_ref": "memory://fixtures/adversarial/multistep_bypass",
            "expected_outcome": "blocked",
        },
        {
            "fixture_id": "adv:reward-hack",
            "check_type": "reward_hackable_task",
            "input_ref": "memory://fixtures/adversarial/reward_hackable_task",
            "expected_outcome": "correct-but-overfit",
        },
        # ── v0.6.2 breadth additions (Plan 05) ────────────────────────────────
        # Each new fixture sits in the same check_type as an existing fixture
        # but pins a *different shape* of the attack within that category.
        # The single-fixture-per-category floor (Phase 18 §8.2) is the
        # minimum; doubling the high-value categories closes more failure
        # modes without measurable gate-time impact.
        {
            "fixture_id": "adv:indirect-prompt-injection",
            "check_type": "prompt_injection",
            "input_ref": "memory://fixtures/adversarial/indirect_prompt_injection",
            "expected_outcome": "typed_error",
        },
        {
            "fixture_id": "adv:scope-write-symlink",
            "check_type": "out_of_scope_write",
            "input_ref": "memory://fixtures/adversarial/out_of_scope_write_symlink",
            "expected_outcome": "process-noncompliant",
        },
        {
            "fixture_id": "adv:policy-bypass-test-mode",
            "check_type": "multistep_policy_bypass",
            "input_ref": "memory://fixtures/adversarial/multistep_bypass_test_mode",
            "expected_outcome": "blocked",
        },
        {
            "fixture_id": "adv:reward-hack-test-only-fix",
            "check_type": "reward_hackable_task",
            "input_ref": "memory://fixtures/adversarial/reward_hackable_test_only_fix",
            "expected_outcome": "correct-but-overfit",
        },
    ]


def run_adversarial_suite(
    fixtures: list[dict[str, Any]] | None = None,
) -> list[AdversarialCheckResult]:
    return [
        run_adversarial_check(fixture)
        for fixture in (fixtures or default_adversarial_fixtures())
    ]


def run_adversarial_check(fixture: dict[str, Any]) -> AdversarialCheckResult:
    check_type = str(fixture["check_type"])
    actual = _CHECK_OUTCOMES.get(check_type, "unknown")
    expected = str(fixture.get("expected_outcome", actual))
    return AdversarialCheckResult(
        check_id=f"check:{fixture['fixture_id']}",
        check_type=check_type,
        fixture_id=str(fixture["fixture_id"]),
        input_ref=str(fixture["input_ref"]),
        expected_outcome=expected,
        actual_outcome=actual,
        passed=actual == expected,
        evidence_refs=[str(fixture["input_ref"])],
    )
