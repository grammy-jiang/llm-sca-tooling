"""Phase 15 cross-repository traversal with is_partial fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm_sca_tooling.blast_radius.models import (
    AmbiguousLinkRecord,
    CrossRepoImpactRecord,
    MatchMethod,
)
from llm_sca_tooling.schemas.enums import GraphEdgeType

if TYPE_CHECKING:
    from llm_sca_tooling.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

_CROSS_REPO_EDGE_TYPES = {
    GraphEdgeType.CONSUMES.value,
    GraphEdgeType.EXPOSES.value,
    GraphEdgeType.FFI.value,
}


def traverse_cross_repo(
    changed_node_ids: list[str],
    graph_store: GraphStore,
    *,
    registered_repo_ids: list[str] | None = None,
    max_hops: int = 2,
    analyser_threshold: float = 0.75,
) -> tuple[list[CrossRepoImpactRecord], list[AmbiguousLinkRecord]]:
    """Traverse cross-repo graph overlay to find consuming repos.

    When the overlay is unavailable or incomplete, returns CrossRepoImpactRecord
    with is_partial=True — never silently skips.

    Returns (cross_repo_records, ambiguous_link_records).
    """
    if not registered_repo_ids:
        logger.info("No registered repos provided; cross-repo traversal skipped.")
        ambiguous = [
            AmbiguousLinkRecord(
                source_node_id=nid,
                target_node_id="<unknown>",
                edge_type=GraphEdgeType.CONSUMES.value,
                confidence=0.0,
                match_method=MatchMethod.CROSS_REPO_UNRESOLVED,
                reason_ambiguous="No registered repos available for cross-repo traversal.",
                recommended_followup="Register consuming repos and re-run blast radius.",
            )
            for nid in changed_node_ids
        ]
        return [], ambiguous

    edge_types = [GraphEdgeType(et) for et in _CROSS_REPO_EDGE_TYPES]
    cross_records: list[CrossRepoImpactRecord] = []
    cross_ambiguous: list[AmbiguousLinkRecord] = []

    try:
        slice_ = graph_store.fetch_ego_graph(
            changed_node_ids,
            depth=max_hops,
            edge_types=edge_types,
        )

        # Group consuming nodes by repo_id
        repo_consumers: dict[str, list[str]] = {}
        for node in slice_.nodes:
            if node.node_id in set(changed_node_ids):
                continue
            repo_id = node.repo.repo_id
            if repo_id not in registered_repo_ids:
                cross_ambiguous.append(
                    AmbiguousLinkRecord(
                        source_node_id=changed_node_ids[0] if changed_node_ids else "?",
                        target_node_id=node.node_id,
                        edge_type=GraphEdgeType.CONSUMES.value,
                        confidence=0.0,
                        match_method=MatchMethod.CROSS_REPO_UNRESOLVED,
                        reason_ambiguous=f"Repo {repo_id!r} not in registered repo list.",
                        recommended_followup="Register this repo to enable full cross-repo impact.",
                    )
                )
                continue
            repo_consumers.setdefault(repo_id, []).append(node.node_id)

        for repo_id, consumers in repo_consumers.items():
            cross_records.append(
                CrossRepoImpactRecord(
                    repo_id=repo_id,
                    consuming_node_ids=consumers,
                    hop_distance=1,
                    is_partial=False,
                    confidence=analyser_threshold,
                )
            )

    except Exception as exc:  # noqa: BLE001
        logger.warning("Cross-repo traversal failed: %s", exc)
        cross_records.append(
            CrossRepoImpactRecord(
                repo_id="<unknown>",
                consuming_node_ids=[],
                hop_distance=0,
                is_partial=True,
                partial_reason=f"Graph overlay traversal failed: {exc}",
                confidence=0.0,
            )
        )

    return cross_records, cross_ambiguous


__all__ = ["traverse_cross_repo"]
