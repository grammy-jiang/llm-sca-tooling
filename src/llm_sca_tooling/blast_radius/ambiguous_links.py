"""Ambiguous link bucket — never merge with confirmed impact."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import AmbiguousLinkRecord


def make_cross_repo_unresolved(
    source_node_id: str, target_repo_id: str
) -> AmbiguousLinkRecord:
    return AmbiguousLinkRecord(
        source_node_id=source_node_id,
        target_node_id=f"repo:{target_repo_id}",
        edge_type="consumes",
        confidence=0.0,
        match_method="cross_repo_unresolved",
        reason_ambiguous="target repo not registered or graph not indexed",
        recommended_followup="register and index the target repo",
    )
