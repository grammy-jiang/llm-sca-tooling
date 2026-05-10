from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.contract_generator import (
    NullContractGenerator,
)
from llm_sca_tooling.workflows.impl_check.grounding import ground_clause
from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    ClauseGrounding,
    CompileStatus,
    ContractArtifact,
    ContractType,
    GroundingMethod,
    RiskClass,
    StaticVerdictRecord,
    VerdictValue,
)
from llm_sca_tooling.workflows.impl_check.static_verdict import (
    evaluate_contract,
    run_stage_6a_probe,
)


def _clause():
    return extract_clauses("doc:s", "The `foo` function must work.\n")[0]


def test_sarif_alert_violated() -> None:
    v = evaluate_contract(_clause(), None, None, sarif_alert_ids=["a:1"])
    assert v.verdict is VerdictValue.VIOLATED


def test_contract_violated() -> None:
    art = NullContractGenerator(last_run_status=VerdictValue.VIOLATED).generate(
        _clause()
    )
    v = evaluate_contract(_clause(), art, None)
    assert v.verdict is VerdictValue.VIOLATED


def test_contract_satisfied() -> None:
    art = NullContractGenerator(last_run_status=VerdictValue.SATISFIED).generate(
        _clause()
    )
    v = evaluate_contract(_clause(), art, None)
    assert v.verdict is VerdictValue.SATISFIED


def test_no_evidence_unknown() -> None:
    v = evaluate_contract(_clause(), None, None)
    assert v.verdict is VerdictValue.UNKNOWN


def test_unverifiable_unknown() -> None:
    c = _clause().model_copy(update={"checkability": CheckabilityValue.UNVERIFIABLE})
    v = evaluate_contract(c, None, None)
    assert v.verdict is VerdictValue.UNKNOWN
    assert v.override_reason == "unverifiable_clause"


def test_compile_failed_unknown() -> None:
    art = ContractArtifact(
        clause_id="clause:x",
        artifact_type=ContractType.SEMGREP,
        compile_status=CompileStatus.FAILED,
    )
    v = evaluate_contract(_clause(), art, None)
    assert v.verdict is VerdictValue.UNKNOWN
    assert v.override_reason == "contract_compile_failed"


def test_test_evidence_satisfied() -> None:
    v = evaluate_contract(_clause(), None, None, test_result_ids=["t:1"])
    assert v.verdict is VerdictValue.SATISFIED


def test_symbol_grounding_satisfied() -> None:
    grounding = ground_clause(_clause(), available_symbol_ids=["pkg.foo"])
    v = evaluate_contract(_clause(), None, grounding)
    assert v.verdict is VerdictValue.SATISFIED


def test_stage6a_cannot_override_violated() -> None:
    c = _clause()
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.VIOLATED)
    g = ClauseGrounding(
        clause_id=c.clause_id, grounding_method=GroundingMethod.REPO_QA, confidence=0.9
    )
    assert run_stage_6a_probe(c, g, s5) is None


def test_stage6a_security_unknown() -> None:
    c = _clause().model_copy(update={"risk_class": RiskClass.SECURITY})
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.UNKNOWN)
    g = ClauseGrounding(
        clause_id=c.clause_id,
        grounding_method=GroundingMethod.REPO_QA,
        confidence=0.9,
        repo_qa_answer_refs=["q:1"],
    )
    out = run_stage_6a_probe(c, g, s5)
    assert out is not None
    assert out.verdict is VerdictValue.UNKNOWN
    assert out.override_reason == "security_clause_requires_hard_evidence"


def test_stage6a_soft_evidence_satisfies_non_security() -> None:
    c = _clause()
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.UNKNOWN)
    g = ClauseGrounding(
        clause_id=c.clause_id,
        grounding_method=GroundingMethod.REPO_QA,
        confidence=0.9,
        repo_qa_answer_refs=["q:1"],
    )
    out = run_stage_6a_probe(c, g, s5)
    assert out is not None
    assert out.verdict is VerdictValue.SATISFIED


def test_stage6a_low_confidence_returns_none() -> None:
    c = _clause()
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.UNKNOWN)
    g = ClauseGrounding(
        clause_id=c.clause_id, grounding_method=GroundingMethod.REPO_QA, confidence=0.4
    )
    assert run_stage_6a_probe(c, g, s5) is None


def test_stage6a_skips_non_repo_qa_grounding() -> None:
    c = _clause()
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.UNKNOWN)
    g = ClauseGrounding(
        clause_id=c.clause_id,
        grounding_method=GroundingMethod.SYMBOL_MATCH,
        confidence=0.9,
    )
    assert run_stage_6a_probe(c, g, s5) is None


def test_stage6a_skips_satisfied_stage5() -> None:
    c = _clause()
    s5 = StaticVerdictRecord(clause_id=c.clause_id, verdict=VerdictValue.SATISFIED)
    g = ClauseGrounding(
        clause_id=c.clause_id, grounding_method=GroundingMethod.REPO_QA, confidence=0.9
    )
    assert run_stage_6a_probe(c, g, s5) is None
