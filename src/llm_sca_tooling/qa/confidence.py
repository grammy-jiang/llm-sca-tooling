"""Question-class confidence rules."""

from __future__ import annotations

from llm_sca_tooling.qa.evidence_assembler import AnswerEvidence, EvidenceType
from llm_sca_tooling.qa.question import QuestionClass

__all__ = ["derive_confidence"]

_ORDER = {"unknown": 0, "heuristic": 1, "analyser": 2, "parser": 3}


def derive_confidence(
    question_class: QuestionClass,
    evidence: list[AnswerEvidence],
    *,
    has_mixed_snapshot: bool = False,
) -> tuple[str, str, str | None]:
    if not evidence:
        return "unknown", "No evidence matched the question.", "No evidence was found."
    if question_class == QuestionClass.behaviour_trace:
        if any(ev.evidence_type == EvidenceType.graph_path for ev in evidence):
            return (
                "heuristic",
                "Behaviour traces are capped at heuristic confidence.",
                "Behaviour-trace ship gate is not met or path evidence is partial.",
            )
        return (
            "unknown",
            "No graph path was found.",
            "No behaviour path evidence was found.",
        )
    if question_class == QuestionClass.contract_check:
        has_doc = any(ev.evidence_type == EvidenceType.document_link for ev in evidence)
        has_sast = any(ev.evidence_type == EvidenceType.sast_alert for ev in evidence)
        if has_doc and has_sast:
            return "analyser", "Document and predicate evidence matched.", None
        if has_doc:
            return (
                "heuristic",
                "Document link matched without predicate evidence.",
                None,
            )
    if question_class in {QuestionClass.file_loc, QuestionClass.symbol_loc}:
        best = max(evidence, key=lambda ev: _ORDER.get(ev.confidence, 0))
        uncertainty = (
            "Evidence comes from mixed snapshots." if has_mixed_snapshot else None
        )
        return best.confidence, f"Best evidence source is {best.source}.", uncertainty
    return (
        "heuristic",
        "Other questions use best-effort keyword evidence.",
        "Question class is OTHER.",
    )
