from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.grounding import ground_clause, ground_clauses
from llm_sca_tooling.workflows.impl_check.models import GroundingMethod


def test_symbol_match_grounding() -> None:
    clauses = extract_clauses("doc:g", "The `login` function must work.\n")
    grounding = ground_clause(clauses[0], available_symbol_ids=["pkg.auth.login"])
    assert grounding.grounding_method is GroundingMethod.SYMBOL_MATCH
    assert grounding.confidence >= 0.7
    assert grounding.symbol_node_ids == ["pkg.auth.login"]


def test_ungrounded_when_no_symbols_no_repo_qa() -> None:
    clauses = extract_clauses("doc:g", "The system must work.\n")
    g = ground_clause(clauses[0])
    assert g.grounding_method is GroundingMethod.UNGROUNDED
    assert g.confidence == 0.0
    assert g.ungrounded_reason


def test_repo_qa_grounding() -> None:
    clauses = extract_clauses("doc:g", "The `foo` function must work.\n")

    def fake_qa(_clause):
        return ["repo-qa:abc"]

    g = ground_clause(clauses[0], available_symbol_ids=[], repo_qa_fn=fake_qa)
    assert g.grounding_method is GroundingMethod.REPO_QA
    assert g.repo_qa_answer_refs == ["repo-qa:abc"]


def test_ground_clauses_returns_list() -> None:
    clauses = extract_clauses("doc:g", "The system must work.\nmust ship.\n")
    out = ground_clauses(clauses)
    assert len(out) == len(clauses)
