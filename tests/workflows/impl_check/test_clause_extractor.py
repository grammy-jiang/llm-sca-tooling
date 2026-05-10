from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.models import CheckabilityValue, RiskClass


def test_atomic_clause_extracted() -> None:
    text = "The `login` function must validate credentials.\n"
    clauses = extract_clauses("doc:1", text)
    assert len(clauses) == 1
    assert clauses[0].atomic
    assert clauses[0].text.startswith("The `login`")
    assert clauses[0].checkability is CheckabilityValue.STATIC


def test_compound_clause_preserved_as_non_atomic() -> None:
    text = "The system must handle errors and notify users and log events.\n"
    clauses = extract_clauses("doc:c", text)
    parents = [c for c in clauses if not c.atomic]
    assert len(parents) == 1
    children = [c for c in clauses if c.parent_clause_id == parents[0].clause_id]
    assert len(children) >= 2


def test_clause_id_stable() -> None:
    text = "The system must work.\n"
    a = extract_clauses("doc:x", text)
    b = extract_clauses("doc:x", text)
    assert a[0].clause_id == b[0].clause_id


def test_no_clauses_when_no_obligation_keywords() -> None:
    assert extract_clauses("doc:n", "Some descriptive text.\nAnother line.\n") == []


def test_target_candidates_extracted() -> None:
    clauses = extract_clauses("doc:t", "The `foo` function must call `bar`.\n")
    assert "foo" in clauses[0].target_candidates
    assert "bar" in clauses[0].target_candidates


def test_risk_class_security() -> None:
    clauses = extract_clauses("doc:s", "The system must encrypt all passwords.\n")
    assert clauses[0].risk_class is RiskClass.SECURITY


def test_risk_class_compliance() -> None:
    clauses = extract_clauses("doc:s", "The system must comply with GDPR policy.\n")
    assert clauses[0].risk_class is RiskClass.COMPLIANCE


def test_risk_class_performance() -> None:
    clauses = extract_clauses("doc:s", "The endpoint must meet latency targets.\n")
    assert clauses[0].risk_class is RiskClass.PERFORMANCE


def test_harness_policy_flag_default_false() -> None:
    clauses = extract_clauses("doc:p", "The system must work.\n")
    assert clauses[0].harness_policy_flag is False


def test_skips_headings_and_blank_lines() -> None:
    text = "# Heading must do\n\nThe system must work.\n"
    clauses = extract_clauses("doc:h", text)
    assert len(clauses) == 1
