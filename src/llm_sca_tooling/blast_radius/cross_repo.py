"""Cross-repo traversal (stub — full overlay requires Phase 2 cross-repo index)."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import CrossRepoImpactRecord


def traverse_cross_repo(
    changed_symbol_ids: list[str],
    *,
    registered_repos: list[str] | None = None,
    overlay_available: bool = False,
) -> tuple[list[CrossRepoImpactRecord], bool]:
    """Return cross-repo impact records and is_partial flag."""
    if not overlay_available or not registered_repos:
        return (
            [
                CrossRepoImpactRecord(
                    repo_id="unknown",
                    repo_path="unknown",
                    is_partial=True,
                    diagnostics=["cross-repo graph overlay not available"],
                )
            ],
            True,
        )
    records: list[CrossRepoImpactRecord] = []
    for repo in registered_repos:
        records.append(
            CrossRepoImpactRecord(
                repo_id=repo,
                repo_path=repo,
                consuming_symbol_ids=changed_symbol_ids[:2],
                interface_type="unknown",
                is_partial=False,
            )
        )
    return records, False
