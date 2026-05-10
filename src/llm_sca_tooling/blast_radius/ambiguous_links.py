"""Phase 15 ambiguous-link bucket helpers."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import AmbiguousLinkRecord, MatchMethod


def make_unresolved_cross_repo_link(
    source_node_id: str,
    target_node_id: str,
    edge_type: str,
    confidence: float,
    reason: str = "",
) -> AmbiguousLinkRecord:
    return AmbiguousLinkRecord(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        confidence=confidence,
        match_method=MatchMethod.CROSS_REPO_UNRESOLVED,
        reason_ambiguous=reason or "Cross-repo target unresolved.",
        recommended_followup="Register target repo and re-index.",
    )


def make_candidate_link(
    source_node_id: str,
    target_node_id: str,
    edge_type: str,
    confidence: float,
    analyser_threshold: float,
) -> AmbiguousLinkRecord:
    return AmbiguousLinkRecord(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        confidence=confidence,
        match_method=MatchMethod.CANDIDATE_EDGE,
        reason_ambiguous=(
            f"Edge confidence {confidence:.2f} below analyser threshold {analyser_threshold:.2f}."
        ),
        recommended_followup="Run analyser-level pass to confirm or reject.",
    )


__all__ = ["make_candidate_link", "make_unresolved_cross_repo_link"]
