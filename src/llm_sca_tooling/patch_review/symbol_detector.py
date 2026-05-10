"""Heuristic changed-symbol detector mapping diff hunks to symbol records."""

from __future__ import annotations

import re
from collections.abc import Iterable

from llm_sca_tooling.patch_review.models import (
    ChangedSymbolRecord,
    ChangeKind,
    ConfidenceLevel,
    DiffRecord,
    HunkRecord,
)

_PY_DEF_RE = re.compile(r"^\s*(?:async\s+def|def|class)\s+(?P<name>[A-Za-z_]\w*)")
_JS_DEF_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s+(?P<f>[A-Za-z_]\w*)|class\s+(?P<c>[A-Za-z_]\w*))"
)
_GENERATED_HINTS = ("_pb2", "_pb.go", ".gen.", ".g.dart", "/generated/", "_pb2_grpc")
_INTERFACE_HINTS = (
    "/routes/",
    "/api/",
    "/handlers/",
    "/controllers/",
    ".proto",
    "openapi",
)


def _detect_symbol_name(line: str, file_path: str) -> tuple[str, str] | None:
    if file_path.endswith(".py"):
        match = _PY_DEF_RE.match(line)
        if match:
            kind = "function" if "def" in line.split("class")[0] else "class"
            if line.lstrip().startswith("class"):
                kind = "class"
            return match.group("name"), kind
    if file_path.endswith((".js", ".ts", ".tsx", ".jsx", ".mjs")):
        match = _JS_DEF_RE.match(line)
        if match:
            name = match.group("f") or match.group("c")
            if name:
                kind = "function" if match.group("f") else "class"
                return name, kind
    return None


def _is_generated(file_path: str) -> bool:
    return any(h in file_path for h in _GENERATED_HINTS)


def _is_interface_boundary(file_path: str) -> bool:
    return any(h in file_path for h in _INTERFACE_HINTS)


def _classify_change(hunk: HunkRecord) -> ChangeKind:
    added = hunk.added_lines
    removed = hunk.removed_lines
    if added and not removed:
        return ChangeKind.ADDED
    if removed and not added:
        return ChangeKind.REMOVED
    sig_added = any("def " in line or "function " in line for line in added)
    sig_removed = any("def " in line or "function " in line for line in removed)
    if sig_added and sig_removed:
        return ChangeKind.MODIFIED_SIGNATURE
    if all(line.lstrip().startswith(('"""', "'''", "#")) for line in added + removed):
        return ChangeKind.MODIFIED_DOCSTRING
    return ChangeKind.MODIFIED_BODY


def detect_changed_symbols(
    diff: DiffRecord,
    *,
    graph_node_ids: dict[str, str] | None = None,
    public_api_paths: Iterable[str] | None = None,
    stale_index: bool = False,
) -> list[ChangedSymbolRecord]:
    """Return changed symbol records for each hunk.

    ``graph_node_ids`` maps ``f"{file_path}:{symbol_name}"`` to a graph node id.
    Unknown mappings produce records with ``confidence=unknown`` rather than
    being silently dropped.
    """
    public_api = set(public_api_paths or ())
    records: list[ChangedSymbolRecord] = []
    graph_lookup = graph_node_ids or {}

    for hunk in diff.hunks:
        sample_lines = list(hunk.added_lines) + list(hunk.removed_lines)
        symbol_name = "<module>"
        symbol_type = "module"
        for line in sample_lines + list(hunk.context_lines):
            detected = _detect_symbol_name(line, hunk.file_path)
            if detected:
                symbol_name, symbol_type = detected
                break

        change_kind = _classify_change(hunk)
        key = f"{hunk.file_path}:{symbol_name}"
        graph_node_id = graph_lookup.get(key)
        if graph_node_id is None and not stale_index:
            confidence = (
                ConfidenceLevel.UNKNOWN
                if symbol_name == "<module>"
                else ConfidenceLevel.HEURISTIC
            )
        else:
            confidence = (
                ConfidenceLevel.UNKNOWN if stale_index else ConfidenceLevel.ANALYSER
            )

        records.append(
            ChangedSymbolRecord(
                diff_id=diff.diff_id,
                file_path=hunk.file_path,
                symbol_path=f"{hunk.file_path}::{symbol_name}",
                symbol_type=symbol_type,
                change_kind=change_kind,
                span_before=(
                    {"start_line": hunk.old_start, "line_count": hunk.old_count}
                    if hunk.old_count
                    else None
                ),
                span_after=(
                    {"start_line": hunk.new_start, "line_count": hunk.new_count}
                    if hunk.new_count
                    else None
                ),
                graph_node_id=graph_node_id,
                confidence=confidence,
                is_generated=_is_generated(hunk.file_path),
                is_public_api=hunk.file_path in public_api,
                is_interface_boundary=_is_interface_boundary(hunk.file_path),
            )
        )
    return records
