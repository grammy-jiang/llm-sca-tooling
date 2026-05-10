from __future__ import annotations

from typing import Any

from llm_sca_tooling.fl.models import LocalisationResult
from llm_sca_tooling.patch_review.models import DryRUNMismatch, MismatchType
from llm_sca_tooling.traces.integration.fl_hook import augment_localisation_with_trace
from llm_sca_tooling.traces.integration.patch_review_hook import mismatch_with_trace_ref
from llm_sca_tooling.traces.models import (
    DivergencePoint,
    TraceDivergenceType,
    TraceLanguage,
    TraceRunResult,
    TraceRunStatus,
)
from llm_sca_tooling.workflows.bug_resolve.gate_runner import run_gates
from llm_sca_tooling.workflows.bug_resolve.models import CertificateConclusion
from llm_sca_tooling.workflows.impl_check.dynamic_verdict import (
    run_dynamic_verdict_hook,
)
from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
)


def _trace_result() -> TraceRunResult:
    return TraceRunResult(
        trace_run_id="trace:1",
        contract_id="contract:1",
        language=TraceLanguage.PYTHON,
        adapter_id="python-sys-settrace",
        status=TraceRunStatus.COMPLETED,
        compressed_trace_ref="trace-compressed:1",
        divergence_points=[
            DivergencePoint(
                trace_run_id="trace:1",
                function_path="pkg.core.target",
                file_path="pkg/core.py",
                line_number=3,
                divergence_type=TraceDivergenceType.MISSING_CALL,
                graph_node_id="node:target",
            )
        ],
        harness_condition_id="hcs:1",
        run_id="trace:1",
    )


def test_fl_hook_adds_trace_suspect_without_replacing_static() -> None:
    result = LocalisationResult()
    augmented = augment_localisation_with_trace(result, _trace_result(), repo_id="repo")
    assert len(augmented.ranked_files) == 1
    assert augmented.ranked_files[0].node_id == "node:target"
    assert augmented.diagnostics[-1]["code"] == "trace_augmented"


def test_impl_check_dynamic_hook_populates_trace_record() -> None:
    clause = Clause(
        clause_id="c1",
        doc_id="d1",
        text="runtime behavior must match",
        checkability=CheckabilityValue.DYNAMIC,
    )
    record = run_dynamic_verdict_hook(clause, lambda _clause: _trace_result())
    assert record.available is True
    assert record.trace_run_id == "trace:1"
    assert record.compressed_trace_ref == "trace-compressed:1"


async def test_bug_resolve_gate_invokes_trace_hook_when_configured() -> None:
    calls: list[dict[str, Any]] = []

    async def gate(_: dict[str, Any]) -> dict[str, Any]:
        return {"pass": True, "ref": "ok"}

    async def trace_gate(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"status": "completed", "compressed_trace_ref": "trace-compressed:1"}

    result = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="diff",
        sarif_gate=gate,
        build_gate=gate,
        test_gate=gate,
        interface_gate=gate,
        certificate_conclusion=CertificateConclusion.PARTIALLY_SUPPORTED,
        trace_gate=trace_gate,
        reproduction_script="repro.py",
        allow_dynamic_trace=True,
    )
    assert calls
    assert result.dynamic_trace_ref == "trace-compressed:1"
    assert result.dynamic_trace_status == "completed"


def test_patch_review_mismatch_accepts_trace_reference() -> None:
    mismatch = DryRUNMismatch(
        diff_id="d1",
        prediction_id="p1",
        mismatch_type=MismatchType.UNEXPECTED_TEST_FAILURE,
    )
    updated = mismatch.model_copy(update={"trace_divergence_ref": "div:1"})
    assert updated.trace_divergence_ref == "div:1"
    payload = mismatch_with_trace_ref(mismatch.model_dump(mode="json"), "div:2")
    assert payload["trace_divergence_ref"] == "div:2"
