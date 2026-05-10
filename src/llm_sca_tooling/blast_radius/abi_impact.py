"""Phase 15 C/C++ ABI impact detection (with fallback when backend absent)."""

from __future__ import annotations

import logging

from llm_sca_tooling.blast_radius.models import ABIChangeType, ABIImpactNote
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord

logger = logging.getLogger(__name__)

_CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"}


def _is_cpp_file(file_path: str) -> bool:
    lower = file_path.lower()
    return any(lower.endswith(ext) for ext in _CPP_EXTENSIONS)


def build_abi_impact_notes(
    changed_records: list[ChangedSymbolRecord],
    *,
    clangd_available: bool = False,
) -> list[ABIImpactNote]:
    """Produce ABIImpactNotes for C/C++ symbol changes.

    When clangd/libclang backend is unavailable, always produce a note with
    abi_change_type=UNKNOWN and an explanatory diagnostic — never silently skip.
    """
    notes: list[ABIImpactNote] = []

    for rec in changed_records:
        if not _is_cpp_file(rec.file_path):
            continue

        if not clangd_available:
            notes.append(
                ABIImpactNote(
                    symbol_node_id=rec.graph_node_id or rec.symbol_path,
                    symbol_path=rec.symbol_path,
                    abi_change_type=ABIChangeType.UNKNOWN,
                    diagnostics=[
                        "libclang/clangd backend unavailable; ABI analysis skipped. "
                        "Manual ABI review required for this C/C++ change."
                    ],
                )
            )
            logger.warning(
                "ABI analysis unavailable for %s (clangd not present)", rec.file_path
            )
            continue

        # When clangd is available, determine ABI change type from record metadata
        from llm_sca_tooling.patch_review.models import ChangeKind  # noqa: PLC0415

        if rec.change_kind == ChangeKind.MODIFIED_SIGNATURE:
            abi_type = ABIChangeType.SIGNATURE_CHANGED
        else:
            abi_type = ABIChangeType.NO_ABI_IMPACT

        notes.append(
            ABIImpactNote(
                symbol_node_id=rec.graph_node_id or rec.symbol_path,
                symbol_path=rec.symbol_path,
                abi_change_type=abi_type,
                confidence=0.75,
                diagnostics=[],
            )
        )

    return notes


__all__ = ["build_abi_impact_notes"]
