"""Tests for the deterministic gate runner."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.workflows.bug_resolve.gate_runner import run_gates
from llm_sca_tooling.workflows.bug_resolve.models import (
    CertificateConclusion,
    TestExecResult,
)
from llm_sca_tooling.workflows.bug_resolve.reproduction_test import (
    build_reproduction_test_record,
)


async def _pass(_: dict[str, Any]) -> dict[str, Any]:
    return {"pass": True, "ref": "ok"}


async def _fail(_: dict[str, Any]) -> dict[str, Any]:
    return {"pass": False, "ref": "bad"}


async def test_all_gates_pass() -> None:
    result = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="--- a\n+++ b\n@@ \n",
        sarif_gate=_pass,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_pass,
    )
    assert result.overall_gate_pass is True
    assert result.block_reasons == []


async def test_sarif_fail_blocks() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_fail,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_pass,
    )
    assert r.overall_gate_pass is False
    assert "new_critical_sarif_alert" in r.block_reasons


async def test_build_fail_blocks() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_pass,
        build_gate=_fail,
        test_gate=_pass,
        interface_gate=_pass,
    )
    assert "build_failed" in r.block_reasons


async def test_interface_fail_blocks() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_pass,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_fail,
    )
    assert "interface_breaking_change" in r.block_reasons


async def test_no_gates_required_blocks() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        require_sarif_gate=True,
        require_interface_gate=True,
    )
    assert r.overall_gate_pass is False
    assert "sarif_gate_unavailable" in r.block_reasons
    assert "interface_gate_unavailable" in r.block_reasons


async def test_repro_test_hard_evidence_failure_blocks() -> None:
    repro = build_reproduction_test_record(
        run_id="r1",
        candidate_index=0,
        pre_fix_result=TestExecResult.FAIL,
        post_fix_result=TestExecResult.FAIL,
        fails_for_expected_reason=True,
    )
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_pass,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_pass,
        reproduction_test=repro,
    )
    assert "reproduction_test_failed_post_fix" in r.block_reasons


async def test_poc_plus_fail_blocks() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_pass,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_pass,
        poc_plus_result=TestExecResult.FAIL,
    )
    assert "poc_plus_failed" in r.block_reasons


async def test_certificate_conclusion_propagated() -> None:
    r = await run_gates(
        run_id="r1",
        candidate_index=0,
        candidate_diff="d",
        sarif_gate=_pass,
        build_gate=_pass,
        test_gate=_pass,
        interface_gate=_pass,
        certificate_conclusion=CertificateConclusion.SUPPORTED,
    )
    assert r.certificate_conclusion is CertificateConclusion.SUPPORTED
