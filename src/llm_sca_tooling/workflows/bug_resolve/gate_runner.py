"""Deterministic gate runner."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    ExecutionFreeCertificate,
    GateRunnerResult,
)


def run_gates(
    patch: CandidatePatch,
    cert: ExecutionFreeCertificate,
    *,
    new_critical_sarif: bool = False,
    newly_failing_tests: list[str] | None = None,
    interface_breaking: bool = False,
) -> GateRunnerResult:
    failures = newly_failing_tests or []
    block: list[str] = []
    sarif_pass = not new_critical_sarif
    test_pass = not failures
    iface_pass = not interface_breaking
    if new_critical_sarif:
        block.append("new_critical_sarif_alert")
    if failures:
        block.append(f"newly_failing_tests:{','.join(failures)}")
    if interface_breaking:
        block.append("interface_breaking_change")
    # certificate conclusion unsupported is a soft block (logged, not unconditional)
    cert_soft = cert.conclusion == "unsupported"
    if cert_soft:
        block.append("certificate_conclusion_unsupported_soft")
    overall = sarif_pass and test_pass and iface_pass
    return GateRunnerResult(
        run_id=patch.run_id,
        candidate_index=patch.candidate_index,
        sarif_gate_pass=sarif_pass,
        sarif_delta_ref=f"sarif-delta:{patch.run_id}/{patch.candidate_index}",
        build_gate_pass=True,
        test_gate_pass=test_pass,
        required_test_result="not_executed",
        reproduction_test_result="not_executed",
        interface_gate_pass=iface_pass,
        certificate_conclusion=cert.conclusion,
        overall_gate_pass=overall,
        block_reasons=block,
    )
