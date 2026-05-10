"""Phase 15 impact group population from traversal results."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import ImpactGroup, ImpactRecord


def group_impact_records(
    records: list[ImpactRecord],
) -> dict[str, list[dict[str, object]]]:
    """Organise ImpactRecords into the eight impact groups.

    Returns a mapping from ImpactGroup value to a list of serialised records.
    """
    groups: dict[str, list[dict[str, object]]] = {g.value: [] for g in ImpactGroup}

    for record in records:
        serialised = record.model_dump(mode="json")
        groups[record.group.value].append(serialised)

    return groups


def count_confirmed(records: list[ImpactRecord]) -> int:
    return sum(1 for r in records if r.confirmed)


def count_ambiguous_in_confirmed(records: list[ImpactRecord]) -> int:
    """Count records that are NOT confirmed (should be zero — they belong in ambiguous_links)."""
    return sum(1 for r in records if not r.confirmed)


__all__ = ["count_confirmed", "group_impact_records"]
