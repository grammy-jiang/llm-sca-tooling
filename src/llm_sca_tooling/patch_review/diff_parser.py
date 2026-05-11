"""Unified diff parser."""

from __future__ import annotations

import hashlib
import re

from llm_sca_tooling.patch_review.models import DiffHunk, DiffRecord


def parse_diff(
    diff_text: str,
    *,
    snapshot_before_id: str | None = None,
    snapshot_after_id: str | None = None,
) -> DiffRecord:
    changed_files: list[str] = []
    hunks: list[DiffHunk] = []
    current_file = ""
    current_hunk: DiffHunk | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
            if current_file not in changed_files:
                changed_files.append(current_file)
        elif line.startswith("@@"):
            match = re.search(r"-(\d+).* \+(\d+)", line)
            old_start = int(match.group(1)) if match else 0
            new_start = int(match.group(2)) if match else 0
            current_hunk = DiffHunk(
                file_path=current_file,
                old_start=old_start,
                new_start=new_start,
            )
            hunks.append(current_hunk)
        elif current_hunk and line.startswith("+") and not line.startswith("+++"):
            current_hunk.added_lines.append(line[1:])
        elif current_hunk and line.startswith("-") and not line.startswith("---"):
            current_hunk.removed_lines.append(line[1:])
    added = sum(len(hunk.added_lines) for hunk in hunks)
    removed = sum(len(hunk.removed_lines) for hunk in hunks)
    diagnostics = [] if hunks else ["no hunks parsed"]
    return DiffRecord(
        diff_id="diff:" + hashlib.sha256(diff_text.encode()).hexdigest()[:16],
        diff_text=diff_text,
        changed_files=changed_files,
        hunks=hunks,
        added_lines=added,
        removed_lines=removed,
        net_lines=added - removed,
        snapshot_before_id=snapshot_before_id,
        snapshot_after_id=snapshot_after_id,
        provenance={"parser": "phase11-unified"},
        diagnostics=diagnostics,
    )
