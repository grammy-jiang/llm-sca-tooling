"""Tests for dynamic verdict stage 6b with trace-derived verdicts."""

from __future__ import annotations

from llm_sca_tooling.traces.models import (
    DivergencePoint,
    TraceDivergenceType,
    TraceLanguage,
    TraceRunResult,
    TraceRunStatus,
)
from llm_sca_tooling.workflows.impl_check.dynamic_verdict import (
    _derive_verdict_from_trace,
    run_dynamic_verdict_hook,
)
from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    VerdictValue,
)


def _make_clause(checkability: CheckabilityValue = CheckabilityValue.DYNAMIC) -> Clause:
    return Clause(
        clause_id="clause:test",
        doc_id="doc:test",
        text="The system must raise an exception on invalid input.",
        checkability=checkability,
    )


def _make_trace_result(
    divergence_points: list[DivergencePoint] | None = None,
) -> TraceRunResult:
    return TraceRunResult(
        trace_run_id="trace:test",
        contract_id="contract:test",
        language=TraceLanguage.PYTHON,
        adapter_id="python-sys-settrace",
        status=TraceRunStatus.COMPLETED,
        harness_condition_id="hcs:test",
        run_id="run:test",
        divergence_points=divergence_points or [],
    )


def _make_divergence(divergence_type: TraceDivergenceType) -> DivergencePoint:
    return DivergencePoint(
        trace_run_id="trace:test",
        function_path="src/foo.py::validate_input",
        divergence_type=divergence_type,
    )


def test_derive_verdict_returns_pass_for_no_divergence() -> None:
    trace = _make_trace_result(divergence_points=[])
    clause = _make_clause(CheckabilityValue.DYNAMIC)
    verdict = _derive_verdict_from_trace(trace, clause)
    assert verdict is VerdictValue.SATISFIED


def test_derive_verdict_returns_failed_for_exception_divergence() -> None:
    trace = _make_trace_result(
        divergence_points=[
            _make_divergence(TraceDivergenceType.EXCEPTION_RAISED_VS_NOT)
        ]
    )
    clause = _make_clause(CheckabilityValue.DYNAMIC)
    verdict = _derive_verdict_from_trace(trace, clause)
    assert verdict is VerdictValue.VIOLATED


def test_derive_verdict_returns_failed_for_missing_call() -> None:
    trace = _make_trace_result(
        divergence_points=[_make_divergence(TraceDivergenceType.MISSING_CALL)]
    )
    clause = _make_clause(CheckabilityValue.DYNAMIC)
    verdict = _derive_verdict_from_trace(trace, clause)
    assert verdict is VerdictValue.VIOLATED


def test_derive_verdict_returns_failed_for_branch_divergence() -> None:
    trace = _make_trace_result(
        divergence_points=[
            _make_divergence(TraceDivergenceType.BRANCH_TAKEN_VS_NOT_TAKEN)
        ]
    )
    clause = _make_clause(CheckabilityValue.HYBRID)
    verdict = _derive_verdict_from_trace(trace, clause)
    assert verdict is VerdictValue.VIOLATED


def test_derive_verdict_returns_unknown_for_static_clause() -> None:
    trace = _make_trace_result(
        divergence_points=[_make_divergence(TraceDivergenceType.MISSING_CALL)]
    )
    clause = _make_clause(CheckabilityValue.STATIC)
    verdict = _derive_verdict_from_trace(trace, clause)
    assert verdict is VerdictValue.UNKNOWN


def test_run_dynamic_verdict_hook_uses_trace_result() -> None:
    trace = _make_trace_result(
        divergence_points=[
            _make_divergence(TraceDivergenceType.EXCEPTION_RAISED_VS_NOT)
        ]
    )
    clause = _make_clause(CheckabilityValue.DYNAMIC)

    def capture_fn(_clause: Clause) -> TraceRunResult:
        return trace

    record = run_dynamic_verdict_hook(clause, capture_fn)
    assert record.verdict is VerdictValue.VIOLATED
    assert record.available is True
    assert record.trace_run_id == "trace:test"


def test_run_dynamic_verdict_hook_pass_when_no_divergence() -> None:
    trace = _make_trace_result(divergence_points=[])
    clause = _make_clause(CheckabilityValue.DYNAMIC)

    record = run_dynamic_verdict_hook(clause, lambda _: trace)
    assert record.verdict is VerdictValue.SATISFIED
    assert record.available is True


def test_run_dynamic_verdict_hook_unknown_without_fn() -> None:
    clause = _make_clause(CheckabilityValue.DYNAMIC)
    record = run_dynamic_verdict_hook(clause)
    assert record.verdict is VerdictValue.UNKNOWN
    assert record.available is False


def test_run_dynamic_verdict_hook_unknown_for_static_clause() -> None:
    trace = _make_trace_result()
    clause = _make_clause(CheckabilityValue.STATIC)
    record = run_dynamic_verdict_hook(clause, lambda _: trace)
    assert record.verdict is VerdictValue.UNKNOWN
    assert record.available is False
