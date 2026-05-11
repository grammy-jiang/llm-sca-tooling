"""ImplementationCheckReport assembler and run_implementation_check entrypoint."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.traces.models import ScopeFilter, TraceRunResult
from llm_sca_tooling.workflows.impl_check.aggregator import aggregate_clause_verdict
from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.contract_generator import (
    ContractArtifactGenerator,
    NullContractGenerator,
    SemgrepContractGenerator,
    generate_contracts_for_clauses,
)
from llm_sca_tooling.workflows.impl_check.dynamic_verdict import (
    run_dynamic_verdict_hook,
)
from llm_sca_tooling.workflows.impl_check.grounding import ground_clauses
from llm_sca_tooling.workflows.impl_check.harness_policy import (
    detect_and_upgrade_harness_policy_clauses,
)
from llm_sca_tooling.workflows.impl_check.ingestion import ingest_markdown
from llm_sca_tooling.workflows.impl_check.intent_graph import build_intent_graph
from llm_sca_tooling.workflows.impl_check.models import (
    ClauseVerdictMatrix,
    ClauseVerdictRecord,
    HarnessPolicyClause,
    ImplementationCheckReport,
    IntentGraph,
    OperationalEvidenceBinding,
    OverallComplianceStatus,
    OverallVerdict,
    RecommendationValue,
    SpecDocument,
    StaticVerdictRecord,
    VerdictValue,
)
from llm_sca_tooling.workflows.impl_check.operational_binding import (
    build_operational_binding,
)
from llm_sca_tooling.workflows.impl_check.static_verdict import (
    evaluate_contract,
    run_stage_6a_probe,
)
from llm_sca_tooling.workflows.impl_check.verdict_matrix import assemble_verdict_matrix

_log = logging.getLogger(__name__)


async def run_implementation_check(
    spec: str,
    *,
    run_id: str | None = None,
    repos: list[str] | None = None,
    policy: dict[str, Any] | None = None,
    null_mode: bool = True,
    generator: ContractArtifactGenerator | None = None,
    available_symbol_ids: list[str] | None = None,
    document_link_ids: list[str] | None = None,
    calibration_ece: float | None = None,
    calibration_family: str | None = None,
    harness_condition_id: str = "hcs:default",
    snapshot_id: str | None = None,
    required_gate_events: list[str] | None = None,
    gate_events_present: dict[str, bool] | None = None,
    trace_service: Any | None = None,
    doc_style: str = "auto",
) -> tuple[ImplementationCheckReport, ClauseVerdictMatrix]:
    """Seven-stage implementation-check DAG.

    Parameters
    ----------
    doc_style:
        Clause-extraction mode passed to ``extract_clauses``.
        ``"auto"`` (default) — RFC mode with automatic fallback to
        architecture mode when clause density is sparse (suitable for
        most inputs).
        ``"rfc"`` — RFC obligation keywords only.
        ``"architecture"`` — also extracts behavioral/structural sentences
        from design docs and phase-based architecture specs.
    """
    if run_id is None:
        run_id = "impl-check:" + hashlib.sha256(spec.encode()).hexdigest()[:16]

    _log.info("impl_check run=%s stage=1 ingestion doc_style=%s", run_id, doc_style)
    spec_doc, raw_text = ingest_markdown(spec)
    doc_id = spec_doc.doc_id

    clauses = extract_clauses(doc_id, raw_text, doc_style=doc_style)
    clauses = detect_and_upgrade_harness_policy_clauses(clauses)
    _log.info(
        "impl_check run=%s stage=1 clauses_extracted=%d doc_style_effective=%s",
        run_id,
        len(clauses),
        doc_style,
    )

    if not clauses:
        matrix = ClauseVerdictMatrix(
            doc_id=doc_id,
            run_id=run_id,
            clause_count=0,
            satisfied_count=0,
            violated_count=0,
            unknown_count=0,
            overall_compliance_status=OverallComplianceStatus.UNKNOWN,
            created_ts=datetime.now(UTC).isoformat(),
        )
        report = _assemble_report(
            run_id, doc_id, harness_condition_id, spec_doc, None, matrix, bindings=[]
        )
        return report, matrix

    _log.info("impl_check run=%s stage=2 intent_graph clauses=%d", run_id, len(clauses))
    intent_graph = build_intent_graph(doc_id, clauses, snapshot_id=snapshot_id)

    _log.info("impl_check run=%s stage=3 contract_generation", run_id)
    if generator is not None:
        gen = generator
    elif null_mode:
        gen = NullContractGenerator()
    else:
        gen = SemgrepContractGenerator()
    artifacts = generate_contracts_for_clauses(clauses, gen)
    artifact_by_clause = {a.clause_id: a for a in artifacts}

    _log.info("impl_check run=%s stage=4 grounding", run_id)
    groundings = ground_clauses(
        clauses, available_symbol_ids, document_link_ids=document_link_ids
    )
    grounding_by_clause = {g.clause_id: g for g in groundings}

    _log.info("impl_check run=%s stage=5 static_verdict", run_id)
    stage5_by_clause: dict[str, list[StaticVerdictRecord]] = {
        c.clause_id: [] for c in clauses
    }
    for clause in clauses:
        artifact = artifact_by_clause.get(clause.clause_id)
        grounding = grounding_by_clause.get(clause.clause_id)
        sarif_ids: list[str] = []
        if isinstance(clause, HarnessPolicyClause):
            gate_ev = gate_events_present or {}
            required = required_gate_events or []
            missing = [e for e in required if not gate_ev.get(e, False)]
            if missing:
                sarif_ids = [f"missing-gate:{e}" for e in missing]
        verdict = evaluate_contract(
            clause, artifact, grounding, sarif_alert_ids=sarif_ids
        )
        stage5_by_clause[clause.clause_id].append(verdict)

    _log.info("impl_check run=%s stage=6a repo_qa_probe", run_id)
    stage6a_by_clause: dict[str, list[StaticVerdictRecord]] = {
        c.clause_id: [] for c in clauses
    }
    for clause in clauses:
        grounding = grounding_by_clause.get(clause.clause_id)
        stage5 = stage5_by_clause[clause.clause_id]
        if stage5 and grounding:
            s6a = run_stage_6a_probe(clause, grounding, stage5[0])
            if s6a:
                stage6a_by_clause[clause.clause_id].append(s6a)

    _log.info("impl_check run=%s stage=6b dynamic_hook", run_id)
    _trace_capture_fn = _make_trace_capture_fn(trace_service, snapshot_id=snapshot_id)
    stage6b_by_clause = {
        c.clause_id: run_dynamic_verdict_hook(c, trace_capture_fn=_trace_capture_fn)
        for c in clauses
    }

    _log.info("impl_check run=%s stage=7 aggregation", run_id)
    verdict_records: list[ClauseVerdictRecord] = []
    for clause in clauses:
        record = aggregate_clause_verdict(
            clause,
            stage5_by_clause[clause.clause_id],
            stage6a_by_clause[clause.clause_id],
            stage6b_by_clause.get(clause.clause_id),
            calibration_ece=calibration_ece,
            calibration_family=calibration_family,
        )
        verdict_records.append(record)

    _bindings: list[OperationalEvidenceBinding] = [
        build_operational_binding(
            run_id,
            clause.clause_id,
            graph_snapshot_id=snapshot_id,
            harness_condition_id=harness_condition_id,
        )
        for clause in clauses
    ]

    matrix = assemble_verdict_matrix(doc_id, run_id, clauses, verdict_records)
    report = _assemble_report(
        run_id,
        doc_id,
        harness_condition_id,
        spec_doc,
        intent_graph,
        matrix,
        bindings=_bindings,
    )
    return report, matrix


def _make_trace_capture_fn(
    trace_service: Any | None,
    *,
    snapshot_id: str | None,
) -> Callable[[Any], Any] | None:
    """Build a trace_capture_fn closure when a trace service is provided."""
    if trace_service is None:
        return None

    def _capture(clause: Any) -> TraceRunResult | None:
        target_symbols = list(getattr(clause, "target_candidates", []))
        scope: dict[str, Any] = {}
        if target_symbols:
            scope["include_functions"] = target_symbols[:10]
        try:
            import asyncio

            coro = trace_service.capture(
                script="",
                scope_filter=ScopeFilter(**scope) if scope else None,
                null_mode=True,
                snapshot_id=snapshot_id,
            )
            if asyncio.iscoroutine(coro):
                loop = asyncio.get_event_loop()
                output = loop.run_until_complete(coro)
            else:
                output = coro
            result = getattr(output, "result", None)
            if isinstance(result, TraceRunResult):
                return result
        except Exception as exc:
            _log.debug("trace capture failed for clause %s: %s", clause.clause_id, exc)
        return None

    return _capture


def _compliance_to_overall_verdict(
    status: OverallComplianceStatus,
) -> OverallVerdict:
    return {
        OverallComplianceStatus.COMPLIANT: OverallVerdict.COMPLIANT,
        OverallComplianceStatus.NON_COMPLIANT: OverallVerdict.NON_COMPLIANT,
        OverallComplianceStatus.PARTIALLY_COMPLIANT: OverallVerdict.PARTIALLY_COMPLIANT,
        OverallComplianceStatus.UNKNOWN: OverallVerdict.UNKNOWN,
    }[status]


def _verdict_to_recommendation(verdict: OverallVerdict) -> RecommendationValue:
    if verdict is OverallVerdict.COMPLIANT:
        return RecommendationValue.MERGE_SUPPORTING
    if verdict is OverallVerdict.NON_COMPLIANT:
        return RecommendationValue.BLOCK
    if verdict is OverallVerdict.PARTIALLY_COMPLIANT:
        return RecommendationValue.REVIEW_REQUIRED
    return RecommendationValue.UNKNOWN


def _assemble_report(
    run_id: str,
    doc_id: str,
    harness_condition_id: str,
    spec_doc: SpecDocument,
    intent_graph: IntentGraph | None,
    matrix: ClauseVerdictMatrix,
    *,
    bindings: list[OperationalEvidenceBinding] | None = None,
) -> ImplementationCheckReport:
    report_id = (
        "impl-check-report:"
        + hashlib.sha256((run_id + doc_id).encode()).hexdigest()[:24]
    )

    per_clause = matrix.per_clause_records
    violated = [
        str(r["clause_id"]) for r in per_clause if r.get("final_verdict") == "violated"
    ]
    unknown = [
        str(r["clause_id"]) for r in per_clause if r.get("final_verdict") == "unknown"
    ]
    satisfied = [
        str(r["clause_id"]) for r in per_clause if r.get("final_verdict") == "satisfied"
    ]

    sec_summary = {
        "count": len(matrix.security_clause_verdicts),
        "verdicts": matrix.security_clause_verdicts,
    }
    hp_summary = {
        "count": len(matrix.harness_policy_verdicts),
        "verdicts": matrix.harness_policy_verdicts,
    }

    overall = _compliance_to_overall_verdict(matrix.overall_compliance_status)
    recommendation = _verdict_to_recommendation(overall)

    uncertainty = ""
    if overall is OverallVerdict.UNKNOWN:
        uncertainty = "insufficient_evidence_for_all_clauses"
    elif overall is OverallVerdict.PARTIALLY_COMPLIANT:
        uncertainty = "some_clauses_unresolved"

    return ImplementationCheckReport(
        report_id=report_id,
        run_id=run_id,
        harness_condition_id=harness_condition_id,
        doc_id=doc_id,
        spec_document_ref=f"doc:{spec_doc.doc_id}",
        intent_graph_ref=intent_graph.graph_id if intent_graph else "",
        clause_verdict_matrix_ref=f"matrix:{run_id}",
        violated_clauses=violated,
        unknown_clauses=unknown,
        satisfied_clauses=satisfied,
        security_clause_summary=sec_summary,
        harness_policy_summary=hp_summary,
        operational_compliance_verdict=overall,
        manifest_regression_verdict=VerdictValue.UNKNOWN,
        overall_verdict=overall,
        recommendation=recommendation,
        uncertainty=uncertainty,
        session_trace_manifest_ref="",
        created_ts=datetime.now(UTC).isoformat(),
        operational_bindings=bindings or [],
    )
