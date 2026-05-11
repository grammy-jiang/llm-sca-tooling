"""AST-diff feature extraction."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    ASTDiffFeatures,
    ChangedSymbolRecord,
    DiffRecord,
)


def extract_ast_diff_features(
    diff: DiffRecord, symbols: list[ChangedSymbolRecord]
) -> ASTDiffFeatures:
    added = "\n".join(line for hunk in diff.hunks for line in hunk.added_lines)
    removed = "\n".join(line for hunk in diff.hunks for line in hunk.removed_lines)
    signature_changed = "def " in added or "def " in removed
    edit_operation = "signature_change" if signature_changed else "body_change"
    if "if " in added:
        edit_operation = "conditional_inserted"
    elif "for " in added or "while " in added:
        edit_operation = "loop_inserted"
    elif "except " in added or "raise " in added:
        edit_operation = "exception_handler_changed"
    generated = any(symbol.is_generated for symbol in symbols)
    return ASTDiffFeatures(
        diff_id=diff.diff_id,
        changed_node_kinds=["function" if signature_changed else "statement"],
        edit_operation=edit_operation,
        touched_symbol_count=len(symbols),
        edit_distance_proxy=diff.added_lines + diff.removed_lines,
        generated_or_stub_flag=generated,
        signature_changed=signature_changed,
        return_type_changed="->" in added or "->" in removed,
        parameter_count_delta=added.count(",") - removed.count(","),
        raises_new_exception="raise " in added,
        security_sensitive_annotation_removed="@secure" in removed,
        confidence="heuristic",
    )
