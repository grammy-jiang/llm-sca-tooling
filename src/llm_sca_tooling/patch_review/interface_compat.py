"""Interface compatibility checks."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import DiffRecord, InterfaceCompatibilityResult


def check_interface_compatibility(diff: DiffRecord) -> InterfaceCompatibilityResult:
    removed = "\n".join(line for hunk in diff.hunks for line in hunk.removed_lines)
    added = "\n".join(line for hunk in diff.hunks for line in hunk.added_lines)
    changed = [
        file for file in diff.changed_files if "api" in file or "openapi" in file
    ]
    breaking: list[str] = []
    candidates: list[str] = []
    if "def " in removed and "def " in added and removed != added:
        breaking.append("interface signature changed")
    if "required" in added:
        breaking.append("required parameter added")
    if changed and not breaking:
        candidates.append("interface file changed")
    return InterfaceCompatibilityResult(
        diff_id=diff.diff_id,
        interface_type="http-rest" if changed else "unknown",
        changed_operations=changed,
        affected_consumers=[f"consumer:{item}" for item in changed],
        breaking_changes=breaking,
        candidate_changes=candidates,
        generated_file_impact=[file for file in diff.changed_files if ".pb." in file],
    )
