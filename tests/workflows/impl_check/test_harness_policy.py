from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.harness_policy import (
    detect_and_upgrade_harness_policy_clauses,
    is_harness_policy_clause,
    to_harness_policy_clause,
)
from llm_sca_tooling.workflows.impl_check.models import HarnessPolicyClause


def test_harness_policy_detected_from_hc1() -> None:
    clauses = extract_clauses("doc:h", "HC1 must be enforced everywhere.\n")
    assert is_harness_policy_clause(clauses[0])


def test_non_harness_clause_not_upgraded() -> None:
    clauses = extract_clauses("doc:h", "The `login` function must work.\n")
    assert not is_harness_policy_clause(clauses[0])


def test_to_harness_policy_clause_sets_flag() -> None:
    clauses = extract_clauses("doc:h", "The harness gate must run before merge.\n")
    upgraded = to_harness_policy_clause(clauses[0])
    assert isinstance(upgraded, HarnessPolicyClause)
    assert upgraded.harness_policy_flag is True
    assert upgraded.policy_source == "AGENTS.md"


def test_detect_and_upgrade_upgrades_relevant() -> None:
    clauses = extract_clauses(
        "doc:h",
        "The `login` function must work.\nThe AGENTS.md policy gate must run.\n",
    )
    upgraded = detect_and_upgrade_harness_policy_clauses(clauses)
    assert any(isinstance(c, HarnessPolicyClause) for c in upgraded)
    assert any(not isinstance(c, HarnessPolicyClause) for c in upgraded)


def test_already_upgraded_passes_through() -> None:
    clauses = extract_clauses("doc:h", "HC2 must be enforced.\n")
    once = detect_and_upgrade_harness_policy_clauses(clauses)
    twice = detect_and_upgrade_harness_policy_clauses(once)
    assert sum(isinstance(c, HarnessPolicyClause) for c in twice) == sum(
        isinstance(c, HarnessPolicyClause) for c in once
    )
