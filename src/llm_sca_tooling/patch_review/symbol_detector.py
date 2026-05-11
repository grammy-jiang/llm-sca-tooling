"""Heuristic changed-symbol detector."""

from __future__ import annotations

import re

from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, DiffRecord


def detect_changed_symbols(diff: DiffRecord) -> list[ChangedSymbolRecord]:
    records: list[ChangedSymbolRecord] = []
    for hunk in diff.hunks:
        body = "\n".join([*hunk.removed_lines, *hunk.added_lines])
        symbol = _symbol_name(body) or f"{hunk.file_path}:unknown"
        generated = _is_generated(hunk.file_path)
        interface = _is_interface_boundary(body, hunk.file_path)
        public_api = symbol.split(".")[-1].startswith(("api_", "public_")) or interface
        change_kind = _change_kind(hunk.removed_lines, hunk.added_lines)
        records.append(
            ChangedSymbolRecord(
                diff_id=diff.diff_id,
                file_path=hunk.file_path,
                symbol_path=symbol,
                symbol_type="function" if "def " in body else "unknown",
                change_kind=change_kind,
                span_before=(hunk.old_start, hunk.old_start + len(hunk.removed_lines)),
                span_after=(hunk.new_start, hunk.new_start + len(hunk.added_lines)),
                graph_node_id=f"node:{hunk.file_path}:{symbol}",
                is_generated=generated,
                is_public_api=public_api,
                is_interface_boundary=interface,
            )
        )
    if not records:
        records.append(
            ChangedSymbolRecord(
                diff_id=diff.diff_id,
                file_path="unknown",
                symbol_path="unknown",
                symbol_type="unknown",
                change_kind="unknown",
                confidence="unknown",
            )
        )
    return records


def _symbol_name(body: str) -> str | None:
    match = re.search(r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", body)
    return match.group(1) if match else None


def _change_kind(removed: list[str], added: list[str]) -> str:
    if removed and not added:
        return "removed"
    if added and not removed:
        return "added"
    if any("def " in line for line in removed + added):
        return "modified_signature"
    if any('"""' in line or "'''" in line for line in removed + added):
        return "modified_docstring"
    return "modified_body"


def _is_generated(path: str) -> bool:
    return any(marker in path for marker in (".pb.", "generated", "_stub"))


def _is_interface_boundary(body: str, path: str) -> bool:
    return (
        any(marker in body for marker in ("@app.", "route(", "openapi"))
        or "api" in path
    )
