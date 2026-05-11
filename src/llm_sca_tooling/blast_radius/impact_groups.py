"""Impact group population from traversal results."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.blast_radius.models import ImpactGroup, ImpactRecord


def group_impacts(
    confirmed: list[ImpactRecord],
    additional_nodes: list[dict[str, Any]] | None = None,
) -> dict[ImpactGroup, list[ImpactRecord]]:
    groups: dict[ImpactGroup, list[ImpactRecord]] = {g: [] for g in ImpactGroup}
    for record in confirmed:
        groups[record.group].append(record)
    # Reclassify DIRECT_CALLERS at hop > 1 into DOWNSTREAM_BEHAVIOURS
    promoted: list[ImpactRecord] = []
    remaining: list[ImpactRecord] = []
    for r in groups[ImpactGroup.direct_callers]:
        if r.hop_distance > 1:
            promoted.append(
                r.model_copy(update={"group": ImpactGroup.downstream_behaviours})
            )
        else:
            remaining.append(r)
    groups[ImpactGroup.direct_callers] = remaining
    groups[ImpactGroup.downstream_behaviours].extend(promoted)
    return groups


def groups_to_dict(
    groups: dict[ImpactGroup, list[ImpactRecord]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        g.value: [r.model_dump(mode="json") for r in records]
        for g, records in groups.items()
    }
