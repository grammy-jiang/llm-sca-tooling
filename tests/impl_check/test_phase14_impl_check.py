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

    # ungrounded clause (no target_candidates)
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
