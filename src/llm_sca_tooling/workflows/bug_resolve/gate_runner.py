"""Deterministic gate runner for the bug-resolve workflow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from llm_sca_tooling.traces.integration.bug_resolve_hook import should_run_trace_gate
from llm_sca_tooling.workflows.bug_resolve.models import (
    CertificateConclusion,
    GateRunnerResult,
    ReproductionTestRecord,
    TestExecResult,
)

GateCallable = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def run_gates(
    *,
    run_id: str,
    candidate_index: int,
    candidate_diff: str,
    sarif_gate: GateCallable | None = None,
    build_gate: GateCallable | None = None,
    test_gate: GateCallable | None = None,
    interface_gate: GateCallable | None = None,
    reproduction_test: ReproductionTestRecord | None = None,
    certificate_conclusion: CertificateConclusion = CertificateConclusion.UNKNOWN,
    poc_plus_result: TestExecResult = TestExecResult.NOT_EXECUTED,
    trace_gate: GateCallable | None = None,
    reproduction_script: str | None = None,
    allow_dynamic_trace: bool = False,
    require_sarif_gate: bool = True,
    require_interface_gate: bool = True,
    payload: dict[str, Any] | None = None,
) -> GateRunnerResult:
    """Run all configured gates and aggregate the verdict.

    Each gate callable is awaited with ``payload`` and returns a dict with
    a boolean ``pass`` key and optional ``ref`` (artefact reference). Missing
    gates are treated as ``unknown`` (``None``) — never as ``pass``.
    """
    base_payload: dict[str, Any] = dict(payload or {})
    base_payload["candidate_diff"] = candidate_diff

    block_reasons: list[str] = []

    sarif_pass: bool | None = None
    sarif_ref: str | None = None
    if sarif_gate is not None:
        result = await sarif_gate(base_payload)
        sarif_pass = bool(result.get("pass"))
        sarif_ref = result.get("ref")
        if not sarif_pass:
            block_reasons.append("new_critical_sarif_alert")
    elif require_sarif_gate:
        sarif_pass = None  # unknown — does not pass
        block_reasons.append("sarif_gate_unavailable")

    build_pass: bool | None = None
    if build_gate is not None:
        result = await build_gate(base_payload)
        build_pass = bool(result.get("pass"))
        if not build_pass:
            block_reasons.append("build_failed")

    test_pass: bool | None = None
    if test_gate is not None:
        result = await test_gate(base_payload)
        test_pass = bool(result.get("pass"))
        if not test_pass:
            block_reasons.append("required_test_failing")

    interface_pass: bool | None = None
    interface_ref: str | None = None
    if interface_gate is not None:
        result = await interface_gate(base_payload)
        interface_pass = bool(result.get("pass"))
        interface_ref = result.get("ref")
        if not interface_pass:
            block_reasons.append("interface_breaking_change")
    elif require_interface_gate:
        interface_pass = None
        block_reasons.append("interface_gate_unavailable")

    required_test_result = TestExecResult.NOT_EXECUTED
    repro_test_result = TestExecResult.NOT_EXECUTED
    if reproduction_test is not None:
        repro_test_result = reproduction_test.post_fix_result
        if reproduction_test.generated_test_is_hard_evidence:
            required_test_result = reproduction_test.post_fix_result
            if reproduction_test.post_fix_result is TestExecResult.FAIL:
                block_reasons.append("reproduction_test_failed_post_fix")

    if poc_plus_result is TestExecResult.FAIL:
        block_reasons.append("poc_plus_failed")

    static_gates_passed = (
        not block_reasons
        and bool(sarif_pass) is True
        and (build_pass is None or build_pass is True)
        and (test_pass is None or test_pass is True)
        and (interface_pass is None or interface_pass is True)
    )
    dynamic_trace_ref: str | None = None
    dynamic_trace_status: str | None = None
    if trace_gate is not None and should_run_trace_gate(
        static_gates_passed=static_gates_passed,
        certificate_conclusion=certificate_conclusion.value,
        reproduction_script=reproduction_script,
        allow_dynamic_trace=allow_dynamic_trace,
    ):
        trace_payload = dict(base_payload)
        trace_payload["reproduction_script"] = reproduction_script
        trace_payload["pre_fix"] = True
        trace_result = await trace_gate(trace_payload)
        dynamic_trace_ref = _trace_ref(trace_result)
        dynamic_trace_status = str(trace_result.get("status") or "unknown")

    overall = static_gates_passed
    return GateRunnerResult(
        run_id=run_id,
        candidate_index=candidate_index,
        sarif_gate_pass=sarif_pass,
        sarif_delta_ref=sarif_ref,
        build_gate_pass=build_pass,
        test_gate_pass=test_pass,
        required_test_result=required_test_result,
        reproduction_test_result=repro_test_result,
        poc_plus_result=poc_plus_result,
        interface_gate_pass=interface_pass,
        interface_compat_ref=interface_ref,
        dynamic_trace_ref=dynamic_trace_ref,
        dynamic_trace_status=dynamic_trace_status,
        certificate_conclusion=certificate_conclusion,
        overall_gate_pass=overall,
        block_reasons=block_reasons,
    )


def _trace_ref(result: dict[str, Any]) -> str | None:
    for key in ("ref", "compressed_trace_ref", "trace_run_id"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    nested = result.get("result")
    if isinstance(nested, dict):
        return _trace_ref(nested)
    return None


__all__ = ["run_gates", "GateCallable"]
