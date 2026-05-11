from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.models import CheckabilityValue, RiskClass


def test_atomic_clause_extracted() -> None:
    text = "The `login` function must validate credentials.\n"
    clauses = extract_clauses("doc:1", text)
    assert len(clauses) == 1
    assert clauses[0].atomic
    assert clauses[0].text.startswith("The `login`")
    assert clauses[0].checkability is CheckabilityValue.STATIC


def test_compound_clause_preserved_as_non_atomic() -> None:
    text = "The system must handle errors and notify users and log events.\n"
    clauses = extract_clauses("doc:c", text)
    parents = [c for c in clauses if not c.atomic]
    assert len(parents) == 1
    children = [c for c in clauses if c.parent_clause_id == parents[0].clause_id]
    assert len(children) >= 2


def test_clause_id_stable() -> None:
    text = "The system must work.\n"
    a = extract_clauses("doc:x", text)
    b = extract_clauses("doc:x", text)
    assert a[0].clause_id == b[0].clause_id


def test_no_clauses_rfc_mode_when_no_obligation_keywords() -> None:
    assert (
        extract_clauses(
            "doc:n", "Some descriptive text.\nAnother line.\n", doc_style="rfc"
        )
        == []
    )


def test_target_candidates_extracted() -> None:
    clauses = extract_clauses("doc:t", "The `foo` function must call `bar`.\n")
    assert "foo" in clauses[0].target_candidates
    assert "bar" in clauses[0].target_candidates


def test_risk_class_security() -> None:
    clauses = extract_clauses("doc:s", "The system must encrypt all passwords.\n")
    assert clauses[0].risk_class is RiskClass.SECURITY


def test_risk_class_compliance() -> None:
    clauses = extract_clauses("doc:s", "The system must comply with GDPR policy.\n")
    assert clauses[0].risk_class is RiskClass.COMPLIANCE


def test_risk_class_performance() -> None:
    clauses = extract_clauses("doc:s", "The endpoint must meet latency targets.\n")
    assert clauses[0].risk_class is RiskClass.PERFORMANCE


def test_harness_policy_flag_default_false() -> None:
    clauses = extract_clauses("doc:p", "The system must work.\n")
    assert clauses[0].harness_policy_flag is False


def test_skips_headings_and_blank_lines() -> None:
    text = "# Heading must do\n\nThe system must work.\n"
    clauses = extract_clauses("doc:h", text)
    assert len(clauses) == 1


# --- Architecture-mode tests ---


def test_arch_mode_extracts_bullet_with_behavioral_verb() -> None:
    text = "## Phase 1\n- Stores `GraphNode` objects in the database.\n"
    clauses = extract_clauses("doc:arch1", text, doc_style="architecture")
    assert any("Stores" in c.text or "stores" in c.text for c in clauses)


def test_arch_mode_extracts_bullet_with_symbol_ref() -> None:
    text = "## Phase 2\n- The `GraphEdge` Pydantic model represents a typed edge.\n"
    clauses = extract_clauses("doc:arch2", text, doc_style="architecture")
    assert any("GraphEdge" in c.target_candidates for c in clauses)


def test_arch_mode_skips_short_bullets() -> None:
    text = "## Phase 3\n- OK.\n- Too short.\n"
    clauses = extract_clauses("doc:arch3", text, doc_style="architecture")
    assert clauses == []


def test_arch_mode_skips_pure_prose_without_verb_or_symbol() -> None:
    text = "This section explains the overall context of the system in general terms.\n"
    clauses = extract_clauses("doc:arch4", text, doc_style="architecture")
    assert clauses == []


def test_auto_mode_falls_back_to_arch_for_sparse_doc() -> None:
    # Build a doc that is > 50 lines but has no obligation keywords —
    # auto mode should invoke architecture extraction.
    lines = [
        f"- Provides feature `F{i}` to the downstream service.\n" for i in range(60)
    ]
    text = "## Components\n" + "".join(lines)
    rfc_clauses = extract_clauses("doc:auto1", text, doc_style="rfc")
    auto_clauses = extract_clauses("doc:auto1", text, doc_style="auto")
    assert len(rfc_clauses) == 0
    assert (
        len(auto_clauses) > 0
    ), "auto mode should have fallen back to architecture mode"


def test_auto_mode_does_not_downgrade_rfc_rich_doc() -> None:
    # A doc with dense obligation keywords should not be modified by auto mode.
    lines = [f"The system must handle case {i}.\n" for i in range(10)]
    text = "".join(lines)
    rfc_clauses = extract_clauses("doc:auto2", text, doc_style="rfc")
    auto_clauses = extract_clauses("doc:auto2", text, doc_style="auto")
    assert len(rfc_clauses) == len(auto_clauses)


def test_arch_mode_deduplicates_with_rfc_clauses() -> None:
    # A line with both an obligation keyword and a behavioral verb should
    # appear only once.
    text = "## Phase 1\n- The system must provide `FeedbackRecord` for storage.\n"
    clauses = extract_clauses("doc:arch5", text, doc_style="architecture")
    ids = [c.clause_id for c in clauses]
    assert len(ids) == len(set(ids)), "Duplicate clause IDs found"
