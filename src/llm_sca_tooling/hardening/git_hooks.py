"""Git hook installer for graph-update triggers."""

from __future__ import annotations

from pathlib import Path

HOOK_MARKER = "# evidence-sca managed hook"
HOOK_END_MARKER = "# evidence-sca managed hook end"
HOOK_BODY = f"{HOOK_MARKER}\nevidence-sca graph-update .\n{HOOK_END_MARKER}\n"


class GitHookInstaller:
    def install(self, repo_path: str | Path) -> list[Path]:
        root = Path(repo_path)
        hooks = root / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        installed: list[Path] = []
        for name in ("post-commit", "post-checkout"):
            path = hooks / name
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            if HOOK_MARKER not in existing:
                prefix = existing if existing else "#!/bin/sh\n"
                if prefix and not prefix.endswith("\n"):
                    prefix += "\n"
                path.write_text(prefix + HOOK_BODY, encoding="utf-8")
            path.chmod(0o755)
            installed.append(path)
        return installed

    def uninstall(self, repo_path: str | Path) -> list[Path]:
        root = Path(repo_path)
        removed: list[Path] = []
        for name in ("post-commit", "post-checkout"):
            path = root / ".git" / "hooks" / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if HOOK_MARKER not in text:
                continue
            before, _marker, tail = text.partition(HOOK_MARKER)
            _managed, end_marker, after = tail.partition(HOOK_END_MARKER)
            remaining = (before + after.removeprefix("\n")).rstrip() + "\n"
            if end_marker and remaining.strip() and remaining.strip() != "#!/bin/sh":
                path.write_text(remaining, encoding="utf-8")
            else:
                path.unlink()
            removed.append(path)
        return removed
