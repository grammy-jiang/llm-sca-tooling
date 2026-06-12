"""Stage 6b dynamic-verdict wiring (gap A2).

Phase 16 shipped `make_dynamic_verdict_from_trace`; `run_implementation_check`
must consume trace-derived verdicts when supplied instead of always calling the
dormant hook.
"""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.impl_check.report import run_implementation_check
from llm_sca_tooling.traces.integration.impl_check_hook import (
    make_dynamic_verdict_from_trace,
)
from llm_sca_tooling.traces.models import CompressedTrace, TraceEvent, TraceRunResult

SPEC = """# Mini spec

- The service must validate user input before authentication.
"""

DOC_ID = "spec:stage6b"


def _trace_result(status: str = "completed") -> TraceRunResult:
    return TraceRunResult(
        trace_run_id="trace:0001",
        contract_id="contract:0001",
        language="python",
        adapter_id="python.sys_monitoring",
        status=status,
        compressed_trace_ref="trace:0001/compressed",
        harness_condition_id="hcs:test",
        run_id="run:test",
    )


def _compressed(relevant: bool) -> CompressedTrace:
    events = (
        [
            TraceEvent(
                event_id="evt:1",
                event_type="call",
                module="service",
                function="validate",
                file_path="src/service.py",
            )
        ]
        if relevant
        else []
    )
    return CompressedTrace(
        trace_run_id="trace:0001",
        raw_artefact_id="artefact:raw:0001",
        executed_path_summary="validate -> authenticate",
        relevant_events=events,
    )


def _matrix_records(sink: dict[str, Any], matrix_ref: str) -> list[dict[str, Any]]:
    return list(sink[matrix_ref]["per_clause_records"])


def test_stage6b_dormant_by_default() -> None:
    sink: dict[str, Any] = {}
    report = run_implementation_check(spec=SPEC, doc_id=DOC_ID, artifact_sink=sink)
    records = _matrix_records(sink, report.clause_verdict_matrix_ref)
    assert records
    assert all(r["stage_6b_verdict"] == "unknown" for r in records)


def test_stage6b_consumes_injected_trace_verdict() -> None:
    baseline = run_implementation_check(spec=SPEC, doc_id=DOC_ID)
    clause_id = (
        baseline.satisfied_clauses
        + baseline.violated_clauses
        + baseline.unknown_clauses
    )[0]

    dynamic = make_dynamic_verdict_from_trace(
        clause_id, _trace_result(), _compressed(relevant=True)
    )
    assert dynamic.available is True
    assert dynamic.verdict == "satisfied"

    sink: dict[str, Any] = {}
    report = run_implementation_check(
        spec=SPEC,
        doc_id=DOC_ID,
        dynamic_verdicts={clause_id: dynamic},
        artifact_sink=sink,
    )
    records = {
        r["clause_id"]: r
        for r in _matrix_records(sink, report.clause_verdict_matrix_ref)
    }
    assert records[clause_id]["stage_6b_verdict"] == "satisfied"


def test_stage6b_not_implemented_trace_stays_dormant() -> None:
    baseline = run_implementation_check(spec=SPEC, doc_id=DOC_ID)
    clause_id = (
        baseline.satisfied_clauses
        + baseline.violated_clauses
        + baseline.unknown_clauses
    )[0]

    dynamic = make_dynamic_verdict_from_trace(
        clause_id, _trace_result(status="not_implemented"), None
    )
    assert dynamic.available is False

    sink: dict[str, Any] = {}
    report = run_implementation_check(
        spec=SPEC,
        doc_id=DOC_ID,
        dynamic_verdicts={clause_id: dynamic},
        artifact_sink=sink,
    )
    records = {
        r["clause_id"]: r
        for r in _matrix_records(sink, report.clause_verdict_matrix_ref)
    }
    assert records[clause_id]["stage_6b_verdict"] == "unknown"
