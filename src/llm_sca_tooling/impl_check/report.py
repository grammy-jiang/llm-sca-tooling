"""Phase 14 implementation-check workflow orchestration."""

from __future__ import annotations

import uuid
from typing import Any

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.impl_check.aggregator import aggregate_verdicts
from llm_sca_tooling.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.impl_check.contract_generator import NullContractGenerator
from llm_sca_tooling.impl_check.dynamic_verdict import run_dynamic_hook
from llm_sca_tooling.impl_check.grounding import ground_clause
from llm_sca_tooling.impl_check.ingestion import ingest_spec
from llm_sca_tooling.impl_check.intent_graph import build_intent_graph
from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseUncertaintyDetail,
    ClauseVerdictRecord,
    HarnessPolicyClause,
    ImplementationCheckReport,
)
from llm_sca_tooling.impl_check.operational_binding import bind_operational_evidence
from llm_sca_tooling.impl_check.static_verdict import (
    run_stage_6a_probe,
    run_static_verdict,
)
from llm_sca_tooling.impl_check.verdict_matrix import build_verdict_matrix


def run_implementation_check(
    *,
    spec: str,
    run_id: str | None = None,
    doc_id: str | None = None,
    artifact_sink: dict[str, Any] | None = None,
    # test injection
    simulate_violation: bool = False,
    simulate_all_unknown: bool = False,
    simulate_harness_policy_violation: bool = False,
    simulate_security_clause: bool = False,
    calibration_available: bool = False,
) -> ImplementationCheckReport:
    run_id = run_id or f"impl-check:{uuid.uuid4().hex[:8]}"
    doc_id = doc_id or f"spec:{uuid.uuid4().hex[:8]}"

    hcs = HarnessConditionSheet.create(run_id=run_id)

    # Stage 1: ingest + extract
    spec_doc = ingest_spec(doc_id=doc_id, source=spec, title="spec")
    clauses = extract_clauses(spec_doc, spec)

    # If no clauses extracted, synthesise one unknown
    if not clauses:
        clauses = [
            Clause(
                clause_id=f"clause:synthetic:{doc_id}",
                doc_id=doc_id,
                text="No verifiable clauses extracted.",
                source_span=(0, len(spec)),
                checkability="unverifiable",
                risk_class="unknown",
                atomic=True,
            )
        ]

    spec_doc = spec_doc.model_copy(update={"clause_count": len(clauses)})

    # Stage 2: intent graph
    intent_graph = build_intent_graph(doc_id, clauses)

    generator = NullContractGenerator()
    verdict_records: list[ClauseVerdictRecord] = []

    for clause in clauses:
        # Stage 4: grounding (skip for unverifiable)
        if isinstance(clause, Clause) and clause.checkability == "unverifiable":
            verdict_records.append(
                ClauseVerdictRecord(
                    clause_id=clause.clause_id,
                    final_verdict="unknown",
                    confidence="unknown",
                    ece_bucket="unknown",
                    stage_5_verdicts=["unknown"],
                    stage_6a_verdicts=["unknown"],
                    stage_6b_verdict="unknown",
                    dominant_evidence="unverifiable_clause",
                    uncertainty_reason="unverifiable",
                )
            )
            continue

        grounding = ground_clause(clause)

        # Stage 3: contract generation
        artifact = generator.generate(clause, grounding)

        # Stage 5: static verdict
        if simulate_all_unknown:
            from llm_sca_tooling.impl_check.models import StaticVerdictRecord

            stage5 = StaticVerdictRecord(
                clause_id=clause.clause_id,
                stage="5",
                verdict="unknown",
                evidence_type="simulated_unknown",
                confidence="unknown",
                ece_bucket="unknown",
            )
        else:
            hp_violation = simulate_harness_policy_violation and (
                isinstance(clause, HarnessPolicyClause) or clause.harness_policy_flag
            )
            stage5 = run_static_verdict(
                clause,
                grounding,
                artifact,
                simulate_violation=simulate_violation,
                simulate_harness_policy_violation=hp_violation,
            )

        # Stage 6a
        stage6a = run_stage_6a_probe(
            clause,
            stage5,
            simulate_security_clause=simulate_security_clause,
        )

        # Stage 6b (dormant)
        stage6b = run_dynamic_hook(clause.clause_id)

        # Stage 7
        record = aggregate_verdicts(
            clause,
            stage5,
            stage6a,
            stage6b,
            calibration_available=calibration_available,
        )
        verdict_records.append(record)

        # Operational binding
        bind_operational_evidence(
            run_id=run_id,
            clause_id=clause.clause_id,
            harness_condition_id=hcs.hcs_id,
        )

    # Verdict matrix
    matrix = build_verdict_matrix(doc_id, run_id, clauses, verdict_records)

    # Report
    violated = [r.clause_id for r in verdict_records if r.final_verdict == "violated"]
    unknown = [r.clause_id for r in verdict_records if r.final_verdict == "unknown"]
    satisfied = [r.clause_id for r in verdict_records if r.final_verdict == "satisfied"]
    overall = matrix.overall_compliance_status
    recommendation = _recommendation(overall)

    # Build {clause_id → Clause} for fast text lookup when populating
    # the structured detail lists.  Clauses are typically <200 per run
    # so a dict comprehension is cheap.
    clauses_by_id = {clause.clause_id: clause for clause in clauses}

    def _detail(record: ClauseVerdictRecord) -> ClauseUncertaintyDetail:
        clause = clauses_by_id.get(record.clause_id)
        return ClauseUncertaintyDetail(
            clause_id=record.clause_id,
            text=clause.text if clause is not None else "",
            final_verdict=record.final_verdict,
            uncertainty_reason=record.uncertainty_reason,
            dominant_evidence=record.dominant_evidence,
            confidence=record.confidence,
        )

    unknown_details = [
        _detail(r) for r in verdict_records if r.final_verdict == "unknown"
    ]
    violated_details = [
        _detail(r) for r in verdict_records if r.final_verdict == "violated"
    ]

    report = ImplementationCheckReport(
        report_id=f"impl-check:{run_id}",
        run_id=run_id,
        harness_condition_id=hcs.hcs_id,
        doc_id=doc_id,
        spec_document_ref=f"spec://{doc_id}",
        intent_graph_ref=f"intent-graph://{intent_graph.graph_id}",
        clause_verdict_matrix_ref=f"matrix://{run_id}",
        violated_clauses=violated,
        unknown_clauses=unknown,
        satisfied_clauses=satisfied,
        unknown_clause_details=unknown_details,
        violated_clause_details=violated_details,
        security_clause_summary=(
            "present" if any(c.risk_class == "security" for c in clauses) else "none"
        ),
        harness_policy_summary=(
            "present" if any(c.harness_policy_flag for c in clauses) else "none"
        ),
        operational_compliance_verdict="operational_check_passed",
        manifest_regression_verdict="not_run",
        overall_verdict=overall,
        recommendation=recommendation,
        uncertainty=_uncertainty(matrix),
        session_trace_manifest_ref=f"trace://{run_id}",
    )

    # Populate artifact sink so resource handlers can serve spec/matrix/graph/trace.
    if artifact_sink is not None:
        artifact_sink[report.spec_document_ref] = spec_doc.model_dump(mode="json")
        artifact_sink[report.intent_graph_ref] = intent_graph.model_dump(mode="json")
        artifact_sink[report.clause_verdict_matrix_ref] = matrix.model_dump(mode="json")
        artifact_sink[report.session_trace_manifest_ref] = {
            "run_id": run_id,
            "status": "session_trace_complete",
            "clause_count": len(clauses),
            "overall_verdict": overall,
            "harness_condition_id": hcs.hcs_id,
        }
        # Expose the harness condition sheet so the caller (e.g. MCP server)
        # can persist it via record_harness_condition and link the run record
        # back to it.  This closes the run-record/harness-condition gap
        # reported in May-2026 docs audit Finding 5.
        artifact_sink[f"harness-condition://{hcs.hcs_id}"] = hcs.model_dump(mode="json")

    return report


def _recommendation(overall: str) -> str:
    if overall == "compliant":
        return "merge-supporting"
    if overall == "non_compliant":
        return "block"
    if overall == "partially_compliant":
        return "review-required"
    return "unknown"


def _uncertainty(matrix: object) -> str:
    parts: list[str] = []
    unk = getattr(matrix, "unknown_count", 0)
    if unk:
        parts.append(f"unknown_clauses:{unk}")
    return ";".join(parts)
