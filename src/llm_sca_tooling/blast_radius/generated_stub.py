"""Phase 15 generated-stub impact detection and reporting."""

from __future__ import annotations

import logging

from llm_sca_tooling.blast_radius.models import (
    GeneratedStubImpactNote,
    GeneratedStubImpactType,
)
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord

logger = logging.getLogger(__name__)


def build_generated_stub_notes(
    diff_id: str,
    changed_records: list[ChangedSymbolRecord],
    *,
    generated_file_allowlist: set[str] | None = None,
) -> list[GeneratedStubImpactNote]:
    """Produce GeneratedStubImpactNotes for generated files touched by this diff.

    Rules:
    - Every generated file produces a note.
    - Direct edits to generated files set manual_edit_policy_flag=True unless in allowlist.
    """
    allowlist = generated_file_allowlist or set()
    notes: list[GeneratedStubImpactNote] = []

    for rec in changed_records:
        if not rec.is_generated:
            continue
        is_manual_violation = rec.file_path not in allowlist
        notes.append(
            GeneratedStubImpactNote(
                diff_id=diff_id,
                generated_file_path=rec.file_path,
                generator_source="",
                source_contract_node_id=rec.graph_node_id,
                impact_type=GeneratedStubImpactType.GENERATED_FILE_DIRECTLY_CHANGED,
                manual_edit_policy_flag=is_manual_violation,
                recommended_action=(
                    "Check policy allowlist before merging."
                    if is_manual_violation
                    else "Verify regeneration is idempotent."
                ),
            )
        )
        if is_manual_violation:
            logger.warning(
                "Manual edit detected on generated file %s (diff=%s)",
                rec.file_path,
                diff_id,
            )

    return notes


__all__ = ["build_generated_stub_notes"]
