"""Heuristic AST-diff feature extractor."""

from __future__ import annotations

import re

from llm_sca_tooling.patch_review.models import (
    ASTDiffFeatures,
    ConfidenceLevel,
    DiffRecord,
    EditOperation,
)

_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)")
_CLASS_RE = re.compile(r"^\s*class\s+[A-Za-z_]\w*")
_RETURN_TYPE_RE = re.compile(r"->\s*([^:]+):")
_GEN_HINTS = ("_pb2", "_pb.go", ".gen.", ".g.dart", "/generated/")
_SECURITY_ANNOTATIONS = (
    "@require_auth",
    "@authenticated",
    "@csrf_exempt",
    "@permission_required",
    "@verify_signature",
)


def _count_params(signature: str) -> int:
    s = signature.strip()
    if not s:
        return 0
    return len([part for part in s.split(",") if part.strip()])


def _signature_changes(added: list[str], removed: list[str]) -> tuple[bool, bool, int]:
    added_defs = [m for m in (_DEF_RE.match(line) for line in added) if m is not None]
    removed_defs = [
        m for m in (_DEF_RE.match(line) for line in removed) if m is not None
    ]
    if not (added_defs and removed_defs):
        return False, False, 0
    a, r = added_defs[0], removed_defs[0]
    sig_changed = a.group(0) != r.group(0)
    a_ret = _RETURN_TYPE_RE.search(a.string or "")
    r_ret = _RETURN_TYPE_RE.search(r.string or "")
    return_changed = (a_ret.group(1) if a_ret else None) != (
        r_ret.group(1) if r_ret else None
    )
    delta = _count_params(a.group(2)) - _count_params(r.group(2))
    return sig_changed, return_changed, delta


def extract_ast_diff_features(
    diff: DiffRecord, *, fallback: bool = False
) -> ASTDiffFeatures:
    added = [line for hunk in diff.hunks for line in hunk.added_lines if line.strip()]
    removed = [
        line for hunk in diff.hunks for line in hunk.removed_lines if line.strip()
    ]

    kinds: list[str] = []
    if any(_DEF_RE.match(line) for line in added):
        kinds.append("function_def")
    if any(_CLASS_RE.match(line) for line in added):
        kinds.append("class_def")
    if any(line.lstrip().startswith(("if ", "elif ")) for line in added):
        kinds.append("conditional")
    if any(line.lstrip().startswith(("for ", "while ")) for line in added):
        kinds.append("loop")
    if any(line.lstrip().startswith(("try", "except", "finally")) for line in added):
        kinds.append("exception_handler")

    sig_changed, ret_changed, param_delta = _signature_changes(added, removed)

    only_added_def = any(_DEF_RE.match(line) for line in added) and not any(
        _DEF_RE.match(line) for line in removed
    )
    only_removed_def = any(_DEF_RE.match(line) for line in removed) and not any(
        _DEF_RE.match(line) for line in added
    )

    if sig_changed:
        op = EditOperation.SIGNATURE_CHANGE
    elif only_added_def:
        op = EditOperation.ADDED_FUNCTION
    elif only_removed_def:
        op = EditOperation.REMOVED_FUNCTION
    elif any(line.lstrip().startswith(("if ", "elif ")) for line in added) and not any(
        line.lstrip().startswith(("if ", "elif ")) for line in removed
    ):
        op = EditOperation.CONDITIONAL_INSERTED
    elif any(
        line.lstrip().startswith(("if ", "elif ")) for line in removed
    ) and not any(line.lstrip().startswith(("if ", "elif ")) for line in added):
        op = EditOperation.CONDITIONAL_REMOVED
    elif any(
        line.lstrip().startswith(("for ", "while ")) for line in added
    ) and not any(line.lstrip().startswith(("for ", "while ")) for line in removed):
        op = EditOperation.LOOP_INSERTED
    elif any(
        line.lstrip().startswith(("for ", "while ")) for line in removed
    ) and not any(line.lstrip().startswith(("for ", "while ")) for line in added):
        op = EditOperation.LOOP_REMOVED
    elif any(
        line.lstrip().startswith(("try", "except", "finally"))
        for line in added + removed
    ):
        op = EditOperation.EXCEPTION_HANDLER_CHANGED
    elif added or removed:
        op = EditOperation.BODY_CHANGE
    else:
        op = EditOperation.OTHER

    raises_new = any(line.lstrip().startswith("raise ") for line in added) and not any(
        line.lstrip().startswith("raise ") for line in removed
    )

    sec_removed = any(
        any(ann in line for ann in _SECURITY_ANNOTATIONS) for line in removed
    ) and not any(any(ann in line for ann in _SECURITY_ANNOTATIONS) for line in added)

    generated = any(any(h in f for h in _GEN_HINTS) for f in diff.changed_files)
    touched_symbols = sum(
        1
        for hunk in diff.hunks
        for line in hunk.added_lines + hunk.removed_lines
        if _DEF_RE.match(line) or _CLASS_RE.match(line)
    )

    return ASTDiffFeatures(
        diff_id=diff.diff_id,
        changed_node_kinds=kinds,
        edit_operation=op,
        touched_symbol_count=touched_symbols,
        edit_distance_proxy=len(added) + len(removed),
        generated_or_stub_flag=generated,
        signature_changed=sig_changed,
        return_type_changed=ret_changed,
        parameter_count_delta=param_delta,
        raises_new_exception=raises_new,
        security_sensitive_annotation_removed=sec_removed,
        confidence=ConfidenceLevel.HEURISTIC if fallback else ConfidenceLevel.ANALYSER,
    )
