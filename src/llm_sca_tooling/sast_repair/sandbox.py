"""Sandbox workspace manager for patch application."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from llm_sca_tooling.sast_repair.models import SandboxResult, SASTPatch


class SandboxManager:
    """Create a sandbox copy of a repo, apply a patch, then clean up."""

    def __init__(self, *, sandbox_root: Path | None = None) -> None:
        self.sandbox_root = (
            Path(sandbox_root)
            if sandbox_root
            else Path(tempfile.mkdtemp(prefix="sca-sb-"))
        )
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._created: list[Path] = []

    def apply_patch(
        self,
        *,
        repo_root: Path,
        patch: SASTPatch,
    ) -> SandboxResult:
        repo_root = Path(repo_root).resolve()
        if not repo_root.exists():
            return SandboxResult(
                alert_id=patch.alert_id,
                sandbox_path=str(self.sandbox_root),
                patch_applied=False,
                apply_error=f"repo_root does not exist: {repo_root}",
                cleanup_policy="always",
            )
        sandbox_path = self.sandbox_root / f"sandbox-{uuid.uuid4().hex[:12]}"
        try:
            shutil.copytree(repo_root, sandbox_path)
        except OSError as exc:
            return SandboxResult(
                alert_id=patch.alert_id,
                sandbox_path=str(sandbox_path),
                patch_applied=False,
                apply_error=f"copytree_failed: {exc}",
                cleanup_policy="always",
            )
        self._created.append(sandbox_path)
        snapshot_id = f"sb:{uuid.uuid4().hex[:16]}"
        applied = True
        apply_error: str | None = None
        if patch.diff_text:
            try:
                _apply_unified_diff(sandbox_path, patch.diff_text)
            except (OSError, ValueError) as exc:
                applied = False
                apply_error = f"apply_failed: {exc}"
        return SandboxResult(
            alert_id=patch.alert_id,
            sandbox_path=str(sandbox_path),
            patch_applied=applied,
            apply_error=apply_error,
            sandbox_snapshot_id=snapshot_id,
            cleanup_policy="always",
        )

    def cleanup(self) -> list[str]:
        diagnostics: list[str] = []
        for path in self._created:
            try:
                shutil.rmtree(path, ignore_errors=False)
            except OSError as exc:
                diagnostics.append(f"cleanup_failed:{path}:{exc}")
        self._created.clear()
        return diagnostics


def _apply_unified_diff(sandbox_path: Path, diff_text: str) -> None:
    """Minimal unified-diff applier for null-mode and simple patch tests."""
    current_file: Path | None = None
    new_lines: list[str] | None = None
    file_lines: list[str] | None = None
    cursor = 0
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ "):
            target = raw_line[4:].strip()
            if target.startswith("b/"):
                target = target[2:]
            current_file = sandbox_path / target
            if not current_file.exists():
                raise ValueError(f"target file missing: {target}")
            file_lines = current_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            cursor = 0
            continue
        if raw_line.startswith("--- ") or raw_line.startswith("diff "):
            continue
        if raw_line.startswith("@@"):
            if file_lines is None or new_lines is None:
                raise ValueError("hunk header before file header")
            try:
                _, after, _ = raw_line.split(" ", 2)
            except ValueError as exc:
                raise ValueError(f"malformed hunk header: {raw_line}") from exc
            after = after.lstrip("+")
            start = int(after.split(",")[0]) - 1
            new_lines.extend(file_lines[cursor:start])
            cursor = start
            continue
        if raw_line.startswith("+"):
            if new_lines is None:
                raise ValueError("addition before file header")
            new_lines.append(raw_line[1:])
            continue
        if raw_line.startswith("-"):
            cursor += 1
            continue
        if (
            raw_line.startswith(" ")
            and new_lines is not None
            and file_lines is not None
        ):
            new_lines.append(raw_line[1:])
            cursor += 1
            continue
    if current_file and new_lines is not None and file_lines is not None:
        new_lines.extend(file_lines[cursor:])
        current_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


__all__ = ["SandboxManager"]
