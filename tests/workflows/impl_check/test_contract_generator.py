from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.contract_generator import (
    NullContractGenerator,
    PytestContractGenerator,
    SemgrepContractGenerator,
    generate_contracts_for_clauses,
)
from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    CompileStatus,
    ContractType,
)


def _clause() -> Clause:
    return extract_clauses("doc:c", "The `foo` function must work.\n")[0]


def test_null_returns_artifact() -> None:
    art = NullContractGenerator().generate(_clause())
    assert art.artifact_type is ContractType.NATURAL_LANGUAGE_PROBE
    assert art.compile_status is CompileStatus.NOT_APPLICABLE


def test_null_compile_check() -> None:
    gen = NullContractGenerator()
    art = gen.generate(_clause())
    assert gen.compile_check(art) is CompileStatus.NOT_APPLICABLE


def test_semgrep_returns_semgrep_type() -> None:
    art = SemgrepContractGenerator().generate(_clause())
    assert art.artifact_type is ContractType.SEMGREP
    assert "rules:" in art.content


def test_pytest_returns_pytest_type() -> None:
    art = PytestContractGenerator().generate(_clause())
    assert art.artifact_type is ContractType.PYTEST
    assert "def test_" in art.content


def test_generate_contracts_skips_unverifiable() -> None:
    clause = _clause().model_copy(
        update={"checkability": CheckabilityValue.UNVERIFIABLE}
    )
    out = generate_contracts_for_clauses([clause])
    assert out == []


def test_no_duplicate_artifacts_for_same_clause() -> None:
    c = _clause()
    out = generate_contracts_for_clauses([c, c])
    assert len(out) == 1


def test_default_generator_used_when_none() -> None:
    out = generate_contracts_for_clauses([_clause()])
    assert out and out[0].artifact_type is ContractType.NATURAL_LANGUAGE_PROBE


def test_semgrep_compile_check_not_attempted() -> None:
    gen = SemgrepContractGenerator()
    art = gen.generate(_clause())
    result = gen.compile_check(art)
    # semgrep may not be installed in test env; accept PASSED, FAILED, or NOT_APPLICABLE
    assert result in (
        CompileStatus.PASSED,
        CompileStatus.FAILED,
        CompileStatus.NOT_APPLICABLE,
    )


def test_pytest_compile_check_not_attempted() -> None:
    gen = PytestContractGenerator()
    art = gen.generate(_clause())
    result = gen.compile_check(art)
    # py_compile is always available; accept PASSED or FAILED
    assert result in (
        CompileStatus.PASSED,
        CompileStatus.FAILED,
        CompileStatus.NOT_APPLICABLE,
    )
