"""Sandbox patch application stub."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sast_repair.models import SandboxResult, SASTPatch


def apply_patch_in_sandbox(
    *, patch: SASTPatch, workspace_root: Path | None = None
) -> SandboxResult:
    root = workspace_root or Path(".agent/eval/sandbox")
    sandbox = root / patch.alert_id.replace(":", "_")
    sandbox.mkdir(parents=True, exist_ok=True)
    return SandboxResult(
        alert_id=patch.alert_id,
        sandbox_path=str(sandbox),
        patch_applied=bool(patch.diff_text or patch.generation_method == "null_repair"),
        apply_error=None,
        sandbox_snapshot_id=f"sandbox:{patch.alert_id}",
    )
