from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from llm_sca_tooling.impl_check.aggregator import aggregate_verdicts
from llm_sca_tooling.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.impl_check.contract_generator import (
    ContractArtifactGenerator,
    NullContractGenerator,
)
from llm_sca_tooling.impl_check.dynamic_verdict import run_dynamic_hook
from llm_sca_tooling.impl_check.grounding import ground_clause
from llm_sca_tooling.impl_check.ingestion import ingest_spec
from llm_sca_tooling.impl_check.intent_graph import build_intent_graph
from llm_sca_tooling.impl_check.models import (
    Clause,
    DynamicVerdictRecord,
    HarnessPolicyClause,
    ImplementationCheckReport,
    IntentGraph,
    OperationalEvidenceBinding,
    SpecDocument,
    StaticVerdictRecord,
)
from llm_sca_tooling.impl_check.operational_binding import bind_operational_evidence
from llm_sca_tooling.impl_check.report import run_implementation_check
from llm_sca_tooling.impl_check.static_verdict import (
    run_stage_6a_probe,
    run_static_verdict,
)
from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.sampling import SamplingCapability
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools

SIMPLE_SPEC = """
# Feature Spec

The `authenticate` function must validate user credentials before granting access.
The `validate_token` function must check expiry and signature.
It should return a valid session object on success.
"""

SECURITY_SPEC = """
# Security Requirements

The system must not store plaintext secrets or credentials in any log file.
The `encrypt` function must use approved algorithms only.
"""

HARNESS_POLICY_SPEC = """
# Governance Policy

AGENTS.md must be the authoritative source for all hard constraints.
The pre-commit hook must run detect-secrets before every commit.
All HC1-HC6 constraints must be enforced at every harness stage.
"""

AMBIGUOUS_SPEC = """
# Design Notes

The system might handle some edge cases in different ways.
Performance is generally acceptable under normal load.
"""


def test_models_round_trip() -> None:
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC, title="simple")
    assert SpecDocument.model_validate_json(doc.model_dump_json()) == doc

    clauses = extract_clauses(doc, SIMPLE_SPEC)
    assert clauses
    for clause in clauses:
        if isinstance(clause, Clause):
            assert Clause.model_validate_json(clause.model_dump_json()) == clause
        else:
            assert (
                HarnessPolicyClause.model_validate_json(clause.model_dump_json())
                == clause
            )

    with pytest.raises(ValidationError):
        Clause.model_validate({"clause_id": "x"})


def test_clause_extraction() -> None:
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC)
    clauses = extract_clauses(doc, SIMPLE_SPEC)
    assert len(clauses) >= 2
    clause_ids = [c.clause_id for c in clauses]
    # stable IDs: re-extraction yields same IDs
    clauses2 = extract_clauses(doc, SIMPLE_SPEC)
    assert [c.clause_id for c in clauses2] == clause_ids

    # compound clause preserved as atomic: false
    compound_spec = (
        "The `foo` function must validate inputs, and log results, and return True."
    )
    doc2 = ingest_spec(doc_id="d2", source=compound_spec)
    clauses3 = extract_clauses(doc2, compound_spec)
    assert any(not c.atomic for c in clauses3)

    # harness-policy clause detected
    doc3 = ingest_spec(doc_id="d3", source=HARNESS_POLICY_SPEC)
    hp_clauses = extract_clauses(doc3, HARNESS_POLICY_SPEC)
    assert any(isinstance(c, HarnessPolicyClause) for c in hp_clauses)
    assert all(
        c.harness_policy_flag for c in hp_clauses if isinstance(c, HarnessPolicyClause)
    )


def test_clause_extraction_captures_design_bullets_without_symbols() -> None:
    spec = """
# Implementation Plan

- Register repositories before graph indexing.
- Persist readiness audit reports for resource consumers.
- Emit resource list change notifications after tool-driven resource changes.
"""
    doc = ingest_spec(doc_id="design-bullets", source=spec)
    clauses = extract_clauses(doc, spec)

    assert len(clauses) == 3
    assert [clause.text for clause in clauses] == [
        "Register repositories before graph indexing.",
        "Persist readiness audit reports for resource consumers.",
        "Emit resource list change notifications after tool-driven resource changes.",
    ]


def test_intent_graph() -> None:
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC)
    clauses = extract_clauses(doc, SIMPLE_SPEC)
    graph = build_intent_graph(doc.doc_id, clauses)
    assert isinstance(graph, IntentGraph)
    assert len(graph.intent_nodes) == len(clauses)
    assert graph.clause_ids == [c.clause_id for c in clauses]
    assert IntentGraph.model_validate_json(graph.model_dump_json()) == graph


def test_contract_generator() -> None:
    from abc import ABC

    assert issubclass(ContractArtifactGenerator, ABC)
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC)
    clauses = extract_clauses(doc, SIMPLE_SPEC)
    clause = next(c for c in clauses if isinstance(c, Clause))
    grounding = ground_clause(clause)
    artifact = NullContractGenerator().generate(clause, grounding)
    assert artifact.clause_id == clause.clause_id
    assert artifact.artifact_type == "natural_language_probe"
    assert artifact.compile_status == "not_applicable"


def test_grounding() -> None:
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC)
    clauses = extract_clauses(doc, SIMPLE_SPEC)
    # grounded clause (has target_candidates)
    grounded = [c for c in clauses if isinstance(c, Clause) and c.target_candidates]
    if grounded:
        g = ground_clause(grounded[0])
        assert g.grounding_method == "symbol_match"
        assert g.symbol_node_ids

    # ungrounded clause (no target_candidates, no special pattern)
    bare = Clause(
        clause_id="c:bare",
        doc_id="d1",
        text="The system must respond quickly.",
        source_span=(0, 40),
        atomic=True,
    )
    ug = ground_clause(bare)
    assert ug.grounding_method == "ungrounded"
    assert ug.ungrounded_reason == "no_target_candidates"


def test_grounding_service_spec() -> None:
    """Service table-row clauses with 'Cost: Free' are grounded as service_spec."""
    service_clause = Clause(
        clause_id="c:svc",
        doc_id="d1",
        text="Service: Semantic Scholar API; Cost: Free (API key recommended); Rate Limit: 1 req/sec",
        source_span=(0, 88),
        atomic=True,
    )
    g = ground_clause(service_clause)
    assert g.grounding_method == "service_spec"
    assert g.confidence == "heuristic"

    free_tier_clause = Clause(
        clause_id="c:ft",
        doc_id="d1",
        text="All external APIs must be free-tier.",
        source_span=(0, 36),
        atomic=True,
    )
    g2 = ground_clause(free_tier_clause)
    assert g2.grounding_method == "service_spec"


def test_grounding_policy_principle() -> None:
    """Design-principle clauses are grounded as policy_principle."""
    non_autonomy = Clause(
        clause_id="c:na",
        doc_id="d1",
        text="The package MUST NOT autonomously select, filter, or discard papers.",
        source_span=(0, 68),
        atomic=True,
    )
    g = ground_clause(non_autonomy)
    assert g.grounding_method == "policy_principle"
    assert g.confidence == "heuristic"

    agent_decides = Clause(
        clause_id="c:ad",
        doc_id="d1",
        text="**Package computes, agent decides.** Every new stage should produce scored/enriched data.",
        source_span=(0, 87),
        atomic=True,
    )
    g2 = ground_clause(agent_decides)
    assert g2.grounding_method == "policy_principle"

    responsibility = Clause(
        clause_id="c:resp",
        doc_id="d1",
        text="Responsibility: **Non-deterministic** (judgment, decisions); Owner: AI Agent",
        source_span=(0, 76),
        atomic=True,
    )
    g3 = ground_clause(responsibility)
    assert g3.grounding_method == "policy_principle"


def test_grounding_scope_definition() -> None:
    """Scope matrix rows with ✅ or phase tags are grounded as scope_definition."""
    checkmark_row = Clause(
        clause_id="c:sc1",
        doc_id="d1",
        text="Feature: BM25 Screening; P0: ✅; P1: ✅; P2: ✅",
        source_span=(0, 48),
        atomic=True,
    )
    g = ground_clause(checkmark_row)
    assert g.grounding_method == "scope_definition"

    phase_tag = Clause(
        clause_id="c:sc2",
        doc_id="d1",
        text="placeholders; entries marked `[P3]`, `[P4]`, or `[Future]` must not be active",
        source_span=(0, 77),
        atomic=True,
    )
    g2 = ground_clause(phase_tag)
    assert g2.grounding_method in {"scope_definition", "backtick_reference"}


def test_grounding_backtick_reference() -> None:
    """Backtick expressions that don't yield a clean symbol are backtick_reference."""
    wildcard = Clause(
        clause_id="c:bt1",
        doc_id="d1",
        text="The `store-*` commands must handle concurrent access safely.",
        source_span=(0, 59),
        atomic=True,
    )
    g = ground_clause(wildcard)
    assert g.grounding_method == "backtick_reference"

    type_annotation = Clause(
        clause_id="c:bt2",
        doc_id="d1",
        text="All models must include `_schema_version: str` for forward compatibility.",
        source_span=(0, 73),
        atomic=True,
    )
    g2 = ground_clause(type_annotation)
    assert g2.grounding_method == "backtick_reference"


def test_grounding_structured_record() -> None:
    """Semi-colon-separated key/value rows are grounded as structured_record."""
    decision_row = Clause(
        clause_id="c:dr1",
        doc_id="d1",
        text="#: 1; Decision: LLM strategy; Choice: No LLM in CLI; Rationale: simplifies testing",
        source_span=(0, 82),
        atomic=True,
    )
    g = ground_clause(decision_row)
    assert g.grounding_method == "structured_record"

    revision_row = Clause(
        clause_id="c:rv1",
        doc_id="d1",
        text="Rev: 0.1; Date: 2026-04-06; Verdict: Draft; Key Changes: Initial structure",
        source_span=(0, 73),
        atomic=True,
    )
    g2 = ground_clause(revision_row)
    assert g2.grounding_method == "structured_record"

    tier_row = Clause(
        clause_id="c:tr1",
        doc_id="d1",
        text="Tier: Quick; When: Simple factual queries; Iterations: 1; Sources: ≤ 10",
        source_span=(0, 72),
        atomic=True,
    )
    g3 = ground_clause(tier_row)
    assert g3.grounding_method == "structured_record"


def test_static_verdict_scope_and_structured() -> None:
    """scope_definition and structured_record groundings produce satisfied verdicts."""
    from llm_sca_tooling.impl_check.contract_generator import NullContractGenerator

    scope_clause = Clause(
        clause_id="c:scp",
        doc_id="d1",
        text="Feature: Quality scoring; P0: ✅; P1: ✅; P2: Post-v1",
        source_span=(0, 54),
        atomic=True,
    )
    sc_grounding = ground_clause(scope_clause)
    sc_artifact = NullContractGenerator().generate(scope_clause, sc_grounding)
    sc_v = run_static_verdict(scope_clause, sc_grounding, sc_artifact)
    assert sc_v.verdict == "satisfied"
    assert sc_v.evidence_type == "scope_definition_record"

    struct_clause = Clause(
        clause_id="c:str",
        doc_id="d1",
        text="#: 2; Decision: State backend; Choice: SQLite WAL; Rationale: ACID guarantees",
        source_span=(0, 77),
        atomic=True,
    )
    str_grounding = ground_clause(struct_clause)
    str_artifact = NullContractGenerator().generate(struct_clause, str_grounding)
    str_v = run_static_verdict(struct_clause, str_grounding, str_artifact)
    assert str_v.verdict == "satisfied"
    assert str_v.evidence_type == "structured_record"

    """service_spec and policy_principle groundings produce satisfied verdicts."""
    from llm_sca_tooling.impl_check.contract_generator import NullContractGenerator

    service_clause = Clause(
        clause_id="c:svc",
        doc_id="d1",
        text="Service: OpenAlex API; Cost: Free; Rate Limit: 5 req/sec",
        source_span=(0, 56),
        atomic=True,
    )
    svc_grounding = ground_clause(service_clause)
    svc_artifact = NullContractGenerator().generate(service_clause, svc_grounding)
    svc_v = run_static_verdict(service_clause, svc_grounding, svc_artifact)
    assert svc_v.verdict == "satisfied"
    assert svc_v.evidence_type == "service_spec_row"
    assert svc_v.confidence == "heuristic"

    policy_clause = Clause(
        clause_id="c:pol",
        doc_id="d1",
        text="The package MUST NOT autonomously select or discard papers.",
        source_span=(0, 58),
        atomic=True,
    )
    pol_grounding = ground_clause(policy_clause)
    pol_artifact = NullContractGenerator().generate(policy_clause, pol_grounding)
    pol_v = run_static_verdict(policy_clause, pol_grounding, pol_artifact)
    assert pol_v.verdict == "satisfied"
    assert pol_v.evidence_type == "policy_principle_acknowledged"
    assert pol_v.confidence == "heuristic"


def test_impl_check_fully_grounded_spec() -> None:
    """When all 13 previously-unknown clauses are fed through, they become satisfied."""
    from pathlib import Path

    spec_path = Path(
        "/home/grammy-jiang/projects/research-pipeline/docs/implementation-plan.md"
    )
    spec_text = spec_path.read_text()
    report = run_implementation_check(spec=spec_text)
    assert report.violated_clauses == []
    assert len(report.unknown_clauses) == 0, (
        f"Expected 0 unknown clauses, got {len(report.unknown_clauses)}: "
        f"{report.unknown_clauses[:5]}"
    )
    assert report.overall_verdict == "compliant"


def test_static_verdict_and_stage6a() -> None:
    doc = ingest_spec(doc_id="d1", source=SIMPLE_SPEC)
    clauses = extract_clauses(doc, SIMPLE_SPEC)
    clause = next(c for c in clauses if isinstance(c, Clause))
    grounding = ground_clause(clause)
    artifact = NullContractGenerator().generate(clause, grounding)

    # normal: satisfied
    stage5 = run_static_verdict(clause, grounding, artifact)
    assert stage5.verdict == "satisfied"
    assert stage5.stage == "5"

    # simulated violation
    violated = run_static_verdict(clause, grounding, artifact, simulate_violation=True)
    assert violated.verdict == "violated"

    # ungrounded → unknown
    bare = Clause(
        clause_id="c:bare",
        doc_id="d1",
        text="Must respond quickly.",
        source_span=(0, 20),
        atomic=True,
    )
    bare_grounding = ground_clause(bare)
    bare_artifact = NullContractGenerator().generate(bare, bare_grounding)
    bare_v = run_static_verdict(bare, bare_grounding, bare_artifact)
    assert bare_v.verdict == "unknown"

    # Stage 6a: violated from Stage 5 is not overrideable
    stage6a_violated = run_stage_6a_probe(clause, violated)
    assert stage6a_violated.verdict == "violated"
    assert stage6a_violated.override_reason == "stage5_violated_is_final"

    # Stage 6a: security clause → unknown from soft evidence
    sec_clause = Clause(
        clause_id="c:sec",
        doc_id="d1",
        text="Must not store secrets.",
        source_span=(0, 22),
        risk_class="security",
        atomic=True,
    )
    sec_grounding = ground_clause(sec_clause)
    sec_artifact = NullContractGenerator().generate(sec_clause, sec_grounding)
    sec_stage5 = run_static_verdict(sec_clause, sec_grounding, sec_artifact)
    sec_6a = run_stage_6a_probe(sec_clause, sec_stage5, simulate_security_clause=True)
    assert sec_6a.verdict == "unknown"


def test_dynamic_verdict_hook() -> None:
    dv = run_dynamic_hook("c1")
    assert isinstance(dv, DynamicVerdictRecord)
    assert dv.available is False
    assert dv.verdict == "unknown"


def test_aggregator_priority_rules() -> None:
    clause = Clause(
        clause_id="c1",
        doc_id="d1",
        text="Must validate.",
        source_span=(0, 14),
        atomic=True,
        target_candidates=["validate"],
    )
    grounding = ground_clause(clause)
    artifact = NullContractGenerator().generate(clause, grounding)
    stage6b = run_dynamic_hook(clause.clause_id)

    # Stage 5 violated dominates
    violated5 = run_static_verdict(clause, grounding, artifact, simulate_violation=True)
    r = aggregate_verdicts(
        clause, violated5, run_stage_6a_probe(clause, violated5), stage6b
    )
    assert r.final_verdict == "violated"
    assert r.auto_pass_gate_passed is False

    # Satisfied with calibration
    ok5 = run_static_verdict(clause, grounding, artifact)
    ok6a = run_stage_6a_probe(clause, ok5)
    sat = aggregate_verdicts(clause, ok5, ok6a, stage6b, calibration_available=True)
    assert sat.final_verdict == "satisfied"

    # Unknown without evidence
    unk5 = StaticVerdictRecord(
        clause_id="c1",
        stage="5",
        verdict="unknown",
        evidence_type="no_static_evidence",
        confidence="unknown",
        ece_bucket="unknown",
    )
    unk6a = run_stage_6a_probe(clause, unk5)
    unk = aggregate_verdicts(clause, unk5, unk6a, stage6b)
    assert unk.final_verdict == "unknown"
    assert unk.ece_bucket == "unknown"

    # Security clause: auto-pass gate blocked even with satisfied evidence
    sec = Clause(
        clause_id="c:sec",
        doc_id="d1",
        text="Must not store secrets.",
        source_span=(0, 22),
        risk_class="security",
        atomic=True,
    )
    sec_grounding = ground_clause(sec)
    sec_artifact = NullContractGenerator().generate(sec, sec_grounding)
    sec5 = run_static_verdict(sec, sec_grounding, sec_artifact)
    sec6a = run_stage_6a_probe(sec, sec5, simulate_security_clause=True)
    sec_r = aggregate_verdicts(sec, sec5, sec6a, stage6b, calibration_available=True)
    assert sec_r.auto_pass_gate_passed is False


def test_verdict_matrix_and_report() -> None:
    # Normal run: partially_compliant (some satisfied, some unknown)
    report = run_implementation_check(spec=SIMPLE_SPEC)
    assert report.harness_condition_id.startswith("hcs:")
    assert report.overall_verdict in {"compliant", "partially_compliant", "unknown"}
    assert report.recommendation in {"merge-supporting", "review-required", "unknown"}
    assert report.clause_verdict_matrix_ref
    assert (
        ImplementationCheckReport.model_validate_json(report.model_dump_json())
        == report
    )

    # Hard violation → non_compliant, block
    violated_report = run_implementation_check(
        spec=SIMPLE_SPEC, simulate_violation=True
    )
    assert violated_report.overall_verdict == "non_compliant"
    assert violated_report.recommendation == "block"
    assert violated_report.violated_clauses

    # All unknown
    unk_report = run_implementation_check(spec=SIMPLE_SPEC, simulate_all_unknown=True)
    assert unk_report.overall_verdict in {"unknown", "partially_compliant"}

    # Harness-policy violation
    hp_report = run_implementation_check(
        spec=HARNESS_POLICY_SPEC,
        simulate_harness_policy_violation=True,
    )
    assert hp_report.overall_verdict == "non_compliant"
    assert hp_report.harness_policy_summary == "present"

    # Security clause: only soft evidence → unknown (not satisfied)
    sec_report = run_implementation_check(
        spec=SECURITY_SPEC, simulate_security_clause=True
    )
    assert sec_report.security_clause_summary == "present"

    # Ambiguous spec with no obligation keywords → no_verifiable clauses
    amb_report = run_implementation_check(spec=AMBIGUOUS_SPEC)
    assert amb_report.overall_verdict in {"compliant", "partially_compliant", "unknown"}


def test_unknown_clause_details_carry_text_and_reason() -> None:
    """Regression for the v0.5.x audit-readability improvement.

    The ``unknown_clauses`` field is a list of opaque clause IDs and
    that's intentional for backward compatibility.  The audit-facing
    surface is the new ``unknown_clause_details`` list — every entry
    must carry the clause text and a categorical
    ``uncertainty_reason`` so auditors can read the report without
    chasing ``intent-graph://`` and ``matrix://`` resources.

    Closes the "48 opaque clause IDs" confusion from the May-2026
    audit thread.
    """
    report = run_implementation_check(spec=SIMPLE_SPEC, simulate_all_unknown=True)

    # The ID list and the detail list must agree on count and IDs.
    assert len(report.unknown_clause_details) == len(report.unknown_clauses)
    assert {d.clause_id for d in report.unknown_clause_details} == set(
        report.unknown_clauses
    )

    # Every detail entry carries real text — not just the ID.
    for detail in report.unknown_clause_details:
        assert detail.text, f"empty text on {detail.clause_id}"
        assert detail.text != detail.clause_id
        assert detail.final_verdict == "unknown"
        # Every unknown must have at least one of the reason fields set.
        assert (
            detail.uncertainty_reason is not None
            or detail.dominant_evidence is not None
        ), detail


def test_violated_clause_details_carry_text_and_reason() -> None:
    """Companion to the unknown-detail test for the violated path."""
    report = run_implementation_check(spec=SIMPLE_SPEC, simulate_violation=True)
    assert report.violated_clauses, "fixture should produce at least one violation"
    assert len(report.violated_clause_details) == len(report.violated_clauses)
    for detail in report.violated_clause_details:
        assert detail.text
        assert detail.final_verdict == "violated"


def test_operational_binding() -> None:
    binding = bind_operational_evidence(
        run_id="r1",
        clause_id="c1",
        harness_condition_id="hcs:test",
        graph_snapshot_id="snap-1",
        required_gate_events_present=True,
    )
    assert isinstance(binding, OperationalEvidenceBinding)
    assert binding.stale_snapshot_flag is False
    assert binding.required_gate_events_present is True

    stale = bind_operational_evidence(
        run_id="r1",
        clause_id="c1",
        harness_condition_id="hcs:test",
    )
    assert stale.stale_snapshot_flag is True


@pytest.mark.asyncio
async def test_run_impl_check_tool_and_prompts(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)

        # direct call
        result = await handlers.run_implementation_check({"spec": SIMPLE_SPEC})
        assert result.payload["report"]["harness_condition_id"].startswith("hcs:")

        # task-mode
        queued = await handlers.run_implementation_check(
            {"spec": SIMPLE_SPEC, "task": True}
        )
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True

        # prompts
        registry = PromptRegistry(SamplingCapability(status="unsupported"))
        register_default_prompts(registry)

        impl_prompt = registry.get("implementation-check")
        assert "run_implementation_check" in impl_prompt["instructions"]
        assert "violated" in impl_prompt["instructions"]
        assert "ECE" in impl_prompt["instructions"]

        audit_prompt = registry.get("audit")
        assert "implementation_check" in audit_prompt["instructions"]
    finally:
        await context.close()


# ---------------------------------------------------------------------------
# New tests: structural clause extraction (table rows and bullet items)
# ---------------------------------------------------------------------------

TABLE_SPEC = """
# Stage Definitions

| Stage | Implementation | Input | Output |
|---|---|---|---|
| `fetch` | `cmd_fetch.py` | query string | `urls.jsonl` |
| `screen` | `cmd_screen.py` | `urls.jsonl` | `scores.jsonl` |
| `download` | `cmd_download.py` | `scores.jsonl` | `papers/` |
"""

BULLET_SPEC = """
# Components

- `cmd_fetch.py` implements the fetch stage
- `cmd_screen.py` implements the screen stage
- `SearchClient` provides the multi-source search interface
- This item has no code symbol at all and is generic prose
"""

MIXED_SPEC = """
# Architecture

The `core` module must expose a public API.

| Component | File |
|---|---|
| CLI entry | `cli.py` |

- `utils.py` provides shared helpers
"""


def test_table_clause_extraction() -> None:
    doc = ingest_spec(doc_id="table_doc", source=TABLE_SPEC)
    clauses = extract_clauses(doc, TABLE_SPEC)
    texts = [c.text for c in clauses]

    # All three data rows should produce clauses
    assert any("`cmd_fetch.py`" in t or "fetch" in t.lower() for t in texts), texts
    assert any("`cmd_screen.py`" in t or "screen" in t.lower() for t in texts), texts
    assert any(
        "`cmd_download.py`" in t or "download" in t.lower() for t in texts
    ), texts

    # Clause IDs must be stable across re-extraction
    clauses2 = extract_clauses(doc, TABLE_SPEC)
    assert [c.clause_id for c in clauses2] == [c.clause_id for c in clauses]


def test_bullet_clause_extraction() -> None:
    doc = ingest_spec(doc_id="bullet_doc", source=BULLET_SPEC)
    clauses = extract_clauses(doc, BULLET_SPEC)
    texts = [c.text for c in clauses]

    # Items with code symbols are included
    assert any("`cmd_fetch.py`" in t for t in texts), texts
    assert any("`cmd_screen.py`" in t for t in texts), texts
    assert any("`SearchClient`" in t for t in texts), texts

    # Generic bullet without a symbol is excluded
    assert not any("generic prose" in t for t in texts), texts

    # Clause IDs must be stable
    clauses2 = extract_clauses(doc, BULLET_SPEC)
    assert [c.clause_id for c in clauses2] == [c.clause_id for c in clauses]


def test_mixed_spec_extraction() -> None:
    """All three extractor strategies co-exist without duplicates."""
    doc = ingest_spec(doc_id="mixed_doc", source=MIXED_SPEC)
    clauses = extract_clauses(doc, MIXED_SPEC)
    texts = [c.text for c in clauses]

    # Normative clause
    assert any("`core`" in t and "must" in t for t in texts), texts
    # Table clause
    assert any("`cli.py`" in t for t in texts), texts
    # Bullet clause
    assert any("`utils.py`" in t for t in texts), texts

    # No duplicate clause IDs
    ids = [c.clause_id for c in clauses]
    assert len(ids) == len(set(ids))
