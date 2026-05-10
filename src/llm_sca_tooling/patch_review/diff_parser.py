"""Unified-diff parser for patch-review."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from llm_sca_tooling.patch_review.models import DiffRecord, HunkRecord

_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<header>.*)$"
)


def _strip_diff_prefix(value: str) -> str:
    if value.startswith(("a/", "b/")):
        return value[2:]
    return value


def parse_unified_diff(
    diff_text: str,
    *,
    diff_id: str | None = None,
    snapshot_before_id: str | None = None,
    snapshot_after_id: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> DiffRecord:
    """Parse a unified diff into a :class:`DiffRecord`.

    The parser is permissive: malformed hunks are reported via diagnostics
    rather than raising. Empty diffs are valid (zero hunks, zero changed files).
    """
    if not isinstance(diff_text, str):
        raise TypeError("diff_text must be a str")

    diagnostics: list[dict[str, Any]] = []
    hunks: list[HunkRecord] = []
    changed_files: list[str] = []
    seen_files: set[str] = set()
    current_file: str | None = None
    current_hunk: dict[str, Any] | None = None
    added = 0
    removed = 0

    def flush_hunk() -> None:
        nonlocal current_hunk
        if current_hunk is not None:
            hunks.append(HunkRecord(**current_hunk))
            current_hunk = None

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            flush_hunk()
            parts = raw_line.split()
            if len(parts) >= 4:
                current_file = _strip_diff_prefix(parts[3])
                if current_file and current_file not in seen_files:
                    seen_files.add(current_file)
                    changed_files.append(current_file)
            else:
                diagnostics.append({"code": "malformed_diff_header", "line": raw_line})
            continue
        if raw_line.startswith("+++ "):
            flush_hunk()
            target = _strip_diff_prefix(raw_line[4:].strip())
            if target == "/dev/null":
                continue
            current_file = target
            if current_file and current_file not in seen_files:
                seen_files.add(current_file)
                changed_files.append(current_file)
            continue
        if raw_line.startswith("--- "):
            flush_hunk()
            continue
        match = _HUNK_RE.match(raw_line)
        if match:
            flush_hunk()
            if current_file is None:
                diagnostics.append({"code": "hunk_without_file", "line": raw_line})
                continue
            current_hunk = {
                "file_path": current_file,
                "old_start": int(match.group("old_start")),
                "old_count": int(match.group("old_count") or "1"),
                "new_start": int(match.group("new_start")),
                "new_count": int(match.group("new_count") or "1"),
                "header": (match.group("header") or "").strip() or None,
                "added_lines": [],
                "removed_lines": [],
                "context_lines": [],
            }
            continue
        if current_hunk is None:
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current_hunk["added_lines"].append(raw_line[1:])
            added += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            current_hunk["removed_lines"].append(raw_line[1:])
            removed += 1
        elif raw_line.startswith(" "):
            current_hunk["context_lines"].append(raw_line[1:])
        else:
            current_hunk["context_lines"].append(raw_line)

    flush_hunk()

    if diff_id is None:
        digest = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        diff_id = f"diff:{digest[:24]}"

    return DiffRecord(
        diff_id=diff_id,
        diff_text=diff_text,
        diff_format="unified",
        changed_files=changed_files,
        hunks=hunks,
        added_lines=added,
        removed_lines=removed,
        net_lines=added - removed,
        snapshot_before_id=snapshot_before_id,
        snapshot_after_id=snapshot_after_id,
        provenance=provenance or {},
        diagnostics=diagnostics,
    )
