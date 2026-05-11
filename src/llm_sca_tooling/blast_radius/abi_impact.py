"""C/C++ ABI impact notes (with fallback when backend unavailable)."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import ABIImpactNote


def compute_abi_impact(
    changed_symbol_ids: list[str],
    *,
    cpp_backend_available: bool = False,
) -> list[ABIImpactNote]:
    notes: list[ABIImpactNote] = []
    for sid in changed_symbol_ids:
        if cpp_backend_available:
            notes.append(
                ABIImpactNote(
                    symbol_node_id=sid,
                    symbol_path=sid.replace("symbol:", ""),
                    abi_change_type="signature_changed",
                    confidence="analyser",
                    diagnostics=[],
                )
            )
        else:
            notes.append(
                ABIImpactNote(
                    symbol_node_id=sid,
                    symbol_path=sid.replace("symbol:", ""),
                    abi_change_type="unknown",
                    confidence="unknown",
                    diagnostics=["libclang/clangd backend not available"],
                )
            )
    return notes
